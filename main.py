import os
import re
import discord
import asyncio
import firebase_admin
import json

from datetime import datetime, timedelta
from discord.ext import commands, tasks
from firebase_admin import credentials, firestore
from keep_alive import keep_alive

## CONSTANTS
bot = commands.Bot("/")
update_interval = 60

timezones = {
	"GMT":	("Greenwich Mean Time",	0),
	"UTC":	("Universal Coordinated Time", 0),
	"ECT":	("European Central Time", +1),
	"EET":	("Eastern European Time", +2),
	"ART":	("(Arabic) Egypt Standard Time", +2),
	"EAT":	("Eastern African Time", +3),
	"MET":	("Middle East Time", +3.5),
	"NET":	("Near East Time", +4),
	"PLT":	("Pakistan Lahore Time", +5),
	"IST":	("India Standard Time",	+5.5),
	"BST":	("Bangladesh Standard Time", +6),
	"VST":	("Vietnam Standard Time", +7),
	"CTT":	("China Taiwan Time", +8),
	"JST":	("Japan Standard Time",	+9),
	"ACT":	("Australia Central Time", +9.5),
	"AET":	("Australia Eastern Time", +10),
	"SST":	("Solomon Standard Time", +11),
	"NST":	("New Zealand Standard Time", +12),
	"MIT":	("Midway Islands Time",	-11),
	"HST":	("Hawaii Standard Time", -10),
	"AST":	("Alaska Standard Time", -9),
	"PST":	("Pacific Standard Time", -8),
	"PNT":	("Phoenix Standard Time", -7),
	"MST":	("Mountain Standard Time", -7),
	"CST":	("Central Standard Time", -6),
	"EST":	("Eastern Standard Time", -5),
	"IET":	("Indiana Eastern Standard Time", -5),
	"PRT":	("Puerto Rico and US Virgin Islands Time", -4),
	"CNT":	("Canada Newfoundland Time", -3.5),
	"AGT":	("Argentina Standard Time",	-3),
	"BET":	("Brazil Eastern Time",	-3),
	"CAT":	("Central African Time", -1)
}

class Event:
	#msg_id = ""
	event_datetime = None
	event_name = ""
	event_description = ""
	#shown_reminder = False
		
	def __init__(self, dt, name, des):
		self.event_datetime = dt
		self.event_name = name
		self.event_description = des
	# STRING FOR THE REPRESENTATION OF THIS EVENT TO BE EVAL()ED
	def __repr__(self):
		s = "Event("
		s += repr(self.event_datetime).replace("datetime.","") + ","
		s += repr(self.event_name) + ","
		s += repr(self.event_description) + ")"
		return s 

class Agenda:
	events = []

	#sorting key/comparator
	def get_datetime(self,event):
		return event.event_datetime
	def sort_events(self):
		self.events.sort(key=self.get_datetime)

	def __repr__(self):
		s = "["
		for i in range(len(self.events)):
			if i == len(self.events) - 1:
				s += repr(self.events[i])
			else:
				s += repr(self.events[i]) + ","
		s += "]"
		return s

	async def to_embed(self, ctx):
		# s = "Date       Time     Name\n"
		dates_str = ""
		times_str = ""
		names_str = ""
		for i in range(len(self.events)):
			j = self.events[i]
			dates_str += date_to_string(j.event_datetime, ctx.guild.id) + "\n" # str(j.event_datetime.date()).replace("-", "/") + "\n"
			times_str += time_to_string(j.event_datetime, ctx.guild.id) + "\n"
			names_str += "__" + str(i+1) + "__ " + j.event_name[:50] + "..." * (len(j.event_name) > 50) + "\n"
			# s += f"{i+1}. {date_str} {time_str} {j.event_name}\n"
		
		embed = discord.Embed(title="Agenda", color=0x00ffff)
		if len(self.events) > 0:
			embed.description = "Here are the upcoming events:"
			for i in range(len(self.events)):
				j = self.events[i]
				field_title = "__" + str(i+1) + ".__ " + j.event_name[:50] + "..." * (len(j.event_name) > 50)
				field_value = f"> {date_to_string(j.event_datetime, ctx.guild.id)} @{time_to_string(j.event_datetime, ctx.guild.id)}"
				
				if not is_valid_datetime(j.event_datetime):
					field_title = "~~" + field_title + "~~"
				embed.add_field(name=field_title, value=field_value, inline=False)
			#1/2/2020 @5:00PM
			# embed.add_field(name="Date", value=dates_str, inline=True)
			# embed.add_field(name="Time", value=times_str, inline=True)
			# embed.add_field(name="Name", value=names_str, inline=True)
		else:
			embed.description = "There is nothing here!"
		
		await ctx.send(embed=embed)
	def add_event(self, event, guild_id,to_sort=False):
		self.events.append(event)
		save_agenda(guild_id)
		if to_sort:
			self.sort_events()

	async def send_notifications(self, event, guild_id, approaching=False):
		#REMOVED: RETURNS TRUE IF SUCCESSFULLY SENT
		"""
		bot
		:
		@here
		event embed

		"""
		date_str = date_to_string(event.event_datetime, guild_id) # str(date_object.date()).replace('-','/')
		time_str = time_to_string(event.event_datetime, guild_id)
		embed = discord.Embed(title=event.event_name, description=event.event_description, color=0x00ff00)
	
		embed.add_field(name="Date", value=date_str, inline=True)
		embed.add_field(name="Time", value=time_str, inline=True)

		posting_channel = get_setting(guild_id, "posting_channel")
		#print(posting_channel)
		if posting_channel != None:
			channel = bot.get_channel(posting_channel)
			if approaching:
				amount = get_setting(guild_id,"reminder_time")
				content_msg = f"An event is approaching in " + str(amount) + " minute(s)!"
			else:
				content_msg = "An event has started!" 

			await channel.send(content=f"@here\n{content_msg}", embed=embed)

class Global:
	# map: key -> value = guild_id -> guild's private agenda
	agendas = {}
	settings = {
		#reminder_time -> int minutes
		#posting_channel -> channel id int
		#time_zone -> string
		#daylight_on -> bool
	}


	def add_agenda(self, guild_id):
		if guild_id not in self.agendas:
			self.agendas[guild_id] = Agenda()
			# self.agendas[guild_id].guild = guild_id

	def get_agenda(self, guild_id):
		if guild_id not in self.agendas:
			return None
		else:
			return self.agendas[guild_id]
	def set_agenda(self,guild_id,value):
		if guild_id not in self.agendas:
			self.add_agenda(guild_id)
		self.agendas[guild_id].events = value
	def sort_agenda(self,guild_id):
		(self.agendas[guild_id]).sort_events()


	@tasks.loop(seconds=update_interval)
	async def update(self):
		#1. loop agenda's events 
		#2. check event deltatime ONLY IF IT IS THE SAME DAY AS TODAY
		#3. if deltatime is <= 0 
		#4. send noti
		for guild_id, agenda_i in self.agendas.items(): 
			max_limit = get_setting(guild_id, "reminder_time")
			for i in agenda_i.events: # 15 minute default
				#COMMENT THIS LATER
				#print(get_deltatime_from_now(i.event_datetime).total_seconds())
				if (max_limit * 60 - update_interval) < get_deltatime_from_now(i.event_datetime).total_seconds() <= (max_limit * 60): # tolerace = just before 14 and 15 inclusive
					if get_setting(guild_id, "reminder_time") != 0:
						await agenda_i.send_notifications(i, guild_id, approaching=True)
				elif -2 < get_deltatime_from_now(i.event_datetime).total_seconds() <= 0:
					await agenda_i.send_notifications(i, guild_id)
						#i.shown_reminder = True
#GLOBAL
bot_global = Global()





def is_valid_datetime(dateT):
	# print(get_deltatime_from_now(dateT).total_seconds())
	# print(date_to_string(dateT), time_to_string(dateT))
	return get_deltatime_from_now(dateT).total_seconds() > 0

def get_deltatime_from_now(dateT):
	# print("GET DELTATIME ", dateT, datetime.now())
	return dateT - datetime.now()

def date_to_string(utc_dt, guild_id): # DT MUST BE A UTC TIME!!!!
	# (YYYY/MM/DD) -> (DD/MM/YYYY)
	tz = get_setting(guild_id,"time_zone")
	daylight_on = get_setting(guild_id, "daylight_on")
	dt = utc_dt + timedelta(hours = timezones[tz.upper()][1] + (1 if daylight_on else 0))
	return str(dt.day) + "/" + str(dt.month) + "/" + str(dt.year)

def time_to_string(utc_tm, guild_id):

	tz = get_setting(guild_id, "time_zone")
	daylight_on = get_setting(guild_id, "daylight_on", False)
	local_tm = utc_tm + timedelta(hours = timezones[tz.upper()][1] + (1 if daylight_on else 0))
	if (local_tm.hour == 0):
		return str(local_tm.hour + 12) + ":" + str(local_tm.minute).zfill(2) + "AM " + tz
	if (local_tm.hour > 12):
		return str(local_tm.hour - 12) + ":" + str(local_tm.minute).zfill(2) + "PM " + tz
	if (local_tm.hour == 12):
		return str(local_tm.hour) + ":" + str(local_tm.minute).zfill(2) + "PM " + tz
	return str(local_tm.hour) + ":" + str(local_tm.minute).zfill(2) + "AM " + tz

def get_setting(guild_id, setting, default = None):
	if guild_id not in bot_global.settings:
		# bot_global.settings[guild_id] = {}
		bot_global.settings[guild_id] = load_settings(guild_id)

	if setting not in bot_global.settings[guild_id]:
		bot_global.settings[guild_id][setting] = default

	return bot_global.settings[guild_id][setting]

def set_setting(guild_id, setting, value, is_init = False):
	if guild_id not in bot_global.settings:
		bot_global.settings[guild_id] = {}

	bot_global.settings[guild_id][setting] = value

	if not is_init:
		save_settings(guild_id)

@bot.event
async def on_ready():
	try:
		agendas_docs = db.collection(u'agendas').stream()
		settings_docs = db.collection(u'settings').stream()

		for agenda_doc in agendas_docs:
			agenda_dict = agenda_doc.to_dict()
			load_events = eval(agenda_dict["events_repr"])
			bot_global.set_agenda(int(agenda_doc.id),load_events)
			bot_global.sort_agenda(int(agenda_doc.id))

		for settings_doc in settings_docs:
			setting_dict = settings_doc.to_dict()
			set_setting(int(settings_doc.id), "posting_channel", int(setting_dict["posting_channel"]) if setting_dict["posting_channel"] != "None" else None, True)
			set_setting(int(settings_doc.id), "time_zone", setting_dict["time_zone"] if setting_dict["time_zone"] != "None" else None, True)
			set_setting(int(settings_doc.id), "daylight_on", setting_dict["daylight_on"] == "True", True)
			set_setting(int(settings_doc.id), "reminder_time", int(setting_dict["reminder_time"]) if setting_dict["reminder_time"] != "None" else None, True)


	except Exception as e:
		print("Something went wrong while retrieving saved data: " + str(e))

	print("Bot has started!")

	#DELAY START TIMER
	# wait until xx:xx:00ms before starting 
	time_delay = (datetime.now() - timedelta(seconds=datetime.now().second) + timedelta(minutes=1)) - datetime.now()
	print("Waiting to recover from offset of: " + str(time_delay.total_seconds()) + "...")
	await asyncio.sleep(time_delay.total_seconds())
	bot_global.update.start()
	print("Timer has started!")
	 	
class Main_Commands():
	def __init__(self, bot):
		self.bot = bot

@bot.command(pass_context=True, aliases=['event','Event','newevent'])
async def newEvent(ctx, *, args=""):
	unset_settings = False
	if args == "":
		await ctx.send("Usage: `/event <name> <date> [time] [description]`")
		return
	if not get_setting(ctx.guild.id,"posting_channel") and not get_setting(ctx.guild.id,"time_zone") and not get_setting(ctx.guild.id,"daylight_on") and not get_setting(ctx.guild.id,"reminder_time"):
		await ctx.send("None of your settings have been configured yet. Use `/setup` to configure them.")
		return
	if not get_setting(ctx.guild.id,"posting_channel"):
		await ctx.send("Your notifications channel has not been configured yet. Use `/set postingchannel #<channelname>` to do so.")
		unset_settings = True
	if not get_setting(ctx.guild.id,"time_zone"):
		await ctx.send("Your timezone has not been set. Use `/set timezone <timezone>`. To see a list of timezones, use `/timezones`")
		unset_settings = True
	if get_setting(ctx.guild.id,"daylight_on") is None: 
		await ctx.send("Your Daylight Savings Time mode has not been set yet. Use `/set daylight <on/off>`")
		unset_settings = True
	if not get_setting(ctx.guild.id,"reminder_time"):
		await ctx.send("Your reminder time has not been set yet. Use `/set remindertime <positive integer minutes>`")
		unset_settings = True
	if unset_settings:
		return
	date_match = re.search('\d{1,2}/\d{1,2}/\d{4}', args)
	#"10:24PM"
	time_match = re.search('\d{1,2}:\d{2}(AM|PM|am|pm|Am|aM|Pm|pM)?', args)
	title = None
	desc = None

	date_str = None
	time_str = None

	day = 0
	month = 0
	year = 0

	hour = 0
	minute = 0

	if date_match != None:
		date_start = date_match.start()
		# date_end = date_match.end()
		date_str = date_match.group()
		date_args = date_str.split("/")

		title = args[0:(date_start - 1)].rstrip()

		day = int(date_args[0])
		month = int(date_args[1])
		year = int(date_args[2])

		args = args.replace(title, '')
		args = args.replace(date_str, '')
	else:
		await ctx.send("Usage: /event name date [time] [description]")
		#await ctx.send("You are missing the date of the event!\nPlease specify one!")
		return
	#print(time_match)
	time_args = None
	if time_match is None:
		time_match = re.search('\d{1,2}:\d{2}(AM|PM|am|pm)?', "12:00am")
	if time_match != None:
		# time_end = time_match.end()
		time_str = time_match.group()
		time_args = time_str.split(":")
		hour = int(time_args[0])
		minute = int(time_args[1][0:2])

		args = args.replace(time_str, '')

	desc = args.rstrip()

	if desc == "":
		desc = "No description."

	''' Make Date and Time match datetime library format '''
	date_object = None
	utc_date_object = None
	try:
		tz = get_setting(ctx.guild.id, "time_zone")
		daylight_on = get_setting(ctx.guild.id, "daylight_on")
		date_object = datetime(year, month, day, hour, minute) # Local time

		suffix = time_args[1][2:4]
		if suffix.lower() == 'pm' and date_object.hour != 12:
			date_object += timedelta(hours = 12) 
		elif suffix.lower() == 'am' and date_object.hour == 12:
			date_object -= timedelta(hours = 12) 
		# local - offset -> UTC
		utc_date_object = date_object - timedelta(hours = timezones[tz.upper()][1] + (1 if daylight_on else 0))
	except Exception as e:
		print(e)
		await ctx.send(f"Your date ({date_str}) and/or time ({time_str}) is not valid!\nMake sure you specify them correctly!")
		return

	if date_object:
		date_str = date_to_string(utc_date_object, ctx.guild.id) # str(date_object.date()).replace('-','/')
		time_str = time_to_string(utc_date_object, ctx.guild.id)
		if not is_valid_datetime(utc_date_object):
			await ctx.send(f"Your date ({date_str}) and/or time ({time_str}) is not valid!\nMake sure you set them to sometime in the future!")
			return
		else:
			new_event = Event(utc_date_object, title, desc)
			an_agenda = bot_global.get_agenda(ctx.guild.id)
			if an_agenda == None:
				bot_global.add_agenda(ctx.guild.id)

			bot_global.get_agenda(ctx.guild.id).add_event(new_event,ctx.guild.id,to_sort=True)

			embed = discord.Embed(title=title, description=desc, color=0x00ff00)
			
			embed.add_field(name="Date", value=date_str, inline=True)
			embed.add_field(name="Time", value=time_str, inline=True)
		
			await ctx.send(embed=embed)

@bot.command(pass_context=True, aliases=['agenda'])
async def showagenda(ctx, arg = " ", value=""):
	if arg.lower() == "clear":
		bot_global.get_agenda(ctx.guild.id).events = []
	if arg.lower() == 'remove':
		try:
			popped = bot_global.get_agenda(ctx.guild.id).events.pop(int(value)-1)
			await ctx.send("Successfully removed: " + popped.event_name +" on " + str(date_to_string(popped.event_datetime,ctx.guild.id)) + " @" + time_to_string(popped.event_datetime,ctx.guild.id))
		except ValueError:
			await ctx.send("Usage: `/agenda remove <event number>`")
		except Exception as e:
			print(e)
			await ctx.send("Event does not exist in that position")
	if not bot_global.get_agenda(ctx.guild.id):
		bot_global.add_agenda(ctx.guild.id)
	await bot_global.get_agenda(ctx.guild.id).to_embed(ctx)

	save_agenda(ctx.guild.id)

@bot.command(pass_context=True, aliases=['postingChannel', 'postchannel', 'postingchannel'])
async def postChannel(ctx, channel_arg = None):
	text_channel_list = []
	for c in ctx.guild.channels:
		if str(c.type) == 'text':
			text_channel_list.append(c)
	
	if channel_arg == None:
		channel_id = get_setting(ctx.guild.id, "posting_channel", None)
		if channel_id != None:
			await ctx.send(f"Your notifications channel is <#{channel_id}>")
		else:
			await ctx.send(f"There is no notifications channel! Set one using `/{ctx.message.content[1:]} channel`!")
	else:
		channel = None
		try:
			channel = await commands.TextChannelConverter().convert(ctx, channel_arg)
		except:
			await ctx.send("Usage: `/set postchannel #<existing channelname>`")
			return
		set_setting(ctx.guild.id, "posting_channel", channel.id)
		await ctx.send(f"Notifications channel has been set successfully to <#{channel.id}>!")

@bot.command(pass_context=True)
async def set(ctx, setting_arg="", value=""):
	if setting_arg == "" or value == "":
		await ctx.send("Usage: `/set <setting name> <value>`")
		return
	if setting_arg.lower() in ['postchannel', 'postingchannel']:
		await postChannel(ctx,value)
	elif setting_arg.lower() == 'daylight':
		new_daylight_on = False
		try:
			if value.lower() in ['on','yes','y','true']:
				new_daylight_on = True
			elif value.lower() in ['off','no','n','false']:
				new_daylight_on = False
			await ctx.send("The daylight savings mode has been successfully turned `" + ("on" if new_daylight_on else "off") + "`!")
		except:
			await ctx.send("Usage: `/set daylight on/off`")
		set_setting(ctx.guild.id,"daylight_on",new_daylight_on)
	elif setting_arg.lower() == 'timezone':
		try:
			if value.upper() in timezones:
				set_setting(ctx.guild.id,"time_zone",value.upper())
				await ctx.send("The timezone has been successfully set to `" + value.upper() + "`")
			else:
				await ctx.send("Uh oh, this timezone does not exist!")
		except:
			await ctx.send("Usage: `/set time_zone <e.g \"EST\">`")
	elif setting_arg.lower() == 'remindertime':
		try:
			value = int(value)
			if value < 0:
				raise ValueError()
			set_setting(ctx.guild.id,"reminder_time",value)
			await ctx.send("The reminder time has been successfully set to `" + str(value) + "` minute(s)")
		except ValueError:
			await ctx.send("Please set the reminder time as a positive integer")
		except:
			await ctx.send("Usage: `/set remindertime <number of minutes (positive integer)>`")
	else:
		await ctx.send("The setting you mentioned does not exist!")
	
async def show_timezones(ctx): # print the embed with all of the timezones
	timezone_embed = discord.Embed(title="Available Timezones", color=0xff00ff)
	s1 = ""
	s2 = ""
	s3 = ""
	for k,v in timezones.items():
		s1 += k + "\n"
		s2 += v[0] + "\n"
		if v[1] >= 0:
			s3 += f"GMT+{v[1]}\n"
		else:
			s3 += f"GMT{v[1]}\n"

	timezone_embed.add_field(name="Abbreviation", value=s1, inline=True)
	timezone_embed.add_field(name="Timezone", value=s2, inline=True)
	timezone_embed.add_field(name="GMT Offset", value=s3, inline=True)
	await ctx.send(embed=timezone_embed)


@bot.command(pass_context=True, aliases=['timezones'])
async def showtimezones(ctx):
	await show_timezones(ctx)


@bot.command(pass_context=True)
async def setup(ctx, timeout = 120.0):
	#prompt timezone "EST"
	notif_channel = None
	time_zone = None
	reminder_time = None
	daylight_on = False

	def check(msg):
		return msg.author == ctx.author and msg.channel == ctx.channel
	
	try:
		await ctx.send("Which channel would you like to receive notifications in? (e.g #general)")

		notif_channel_res = await bot.wait_for('message', check=check, timeout=120.0)
		notif_channel = (await commands.TextChannelConverter().convert(ctx, notif_channel_res.content)).id
	except asyncio.TimeoutError:
		await ctx.send("You did not respond in time. Please run `/setup` again!")
		return
	except:
		await ctx.send("Invalid channel. Please run `/setup` again!")
		return

	try:
		await ctx.send("What is the timezone?")
		await show_timezones(ctx)
		time_zone = (await bot.wait_for('message', check=check, timeout=120.0)).content
		time_zone = time_zone.upper()
		if time_zone not in timezones:
			raise Exception("Invalid time zone!") 
	except asyncio.TimeoutError:
		await ctx.send("You did not respond in time. Please run `/setup` again!")
		return
	except:
		await ctx.send("Invalid time zone! Please run `/setup` again!")
		return

	try:
		await ctx.send("Is Daylight Savings Time applied? (y/n)")
		daylight_on = (await bot.wait_for('message', check=check, timeout=120.0)).content.lower() == 'y'
		
	except asyncio.TimeoutError:
		await ctx.send("You did not respond in time. Please run `/setup` again!")
		return
	except:
		await ctx.send("Invalid value. Please run `/setup` again!")
		return

	try:
		await ctx.send("How many minutes early would you like to receive a reminder for every event?")

		reminder_time = int((await bot.wait_for('message', check=check, timeout=120.0)).content)
	except asyncio.TimeoutError:
		await ctx.send("You did not respond in time. Please run `/setup` again!")
		return
	except TypeError:
		reminder_time = 0
		await ctx.send("The time was set to 0 minutes by default since we could not parse the input.")
	
	set_setting(ctx.guild.id, "posting_channel", notif_channel)
	set_setting(ctx.guild.id, "time_zone", time_zone.upper())
	set_setting(ctx.guild.id, "daylight_on", daylight_on)
	set_setting(ctx.guild.id, "reminder_time", reminder_time)

	bot_global.add_agenda(ctx.guild.id)

	confirmation_embed = discord.Embed(title="Your Agenda Settings", color=0xffff00)
			
	confirmation_embed.add_field(name="Posting Channel", value="<#" + str(notif_channel) + ">", inline=True)
	confirmation_embed.add_field(name="Remind Within", value=f"{reminder_time} min(s)", inline=True)
	confirmation_embed.add_field(name="Time Zone", value=time_zone, inline=True)
	confirmation_embed.add_field(name="Daylight Savings", value="On" if daylight_on else "Off", inline=True)
	await ctx.send(content="Your agenda has been successfully set up!", embed=confirmation_embed)

@bot.command(pass_context=True)
async def settings(ctx,arg=""):
	if arg.lower() == "clear":
		set_setting(ctx.guild.id, "posting_channel",None)
		set_setting(ctx.guild.id, "time_zone",None)
		set_setting(ctx.guild.id, "daylight_on",None)
		set_setting(ctx.guild.id, "reminder_time",None)

	settings_embed = discord.Embed(title="Your Agenda Settings", color=0xffff00)

	notif_channel = get_setting(ctx.guild.id, "posting_channel")
	time_zone = get_setting(ctx.guild.id, "time_zone")
	daylight_on = get_setting(ctx.guild.id, "daylight_on")
	reminder_time = get_setting(ctx.guild.id, "reminder_time")
			
	settings_embed.add_field(name="Posting Channel", value="<#" + str(notif_channel) + ">", inline=True)
	settings_embed.add_field(name="Remind Within", value=f"{reminder_time} min(s)", inline=True)
	settings_embed.add_field(name="Time Zone", value=time_zone, inline=True)
	settings_embed.add_field(name="Daylight Savings", value="On" if daylight_on else "Off" if daylight_on == False else "None", inline=True)

	await ctx.send(embed=settings_embed)
	
@bot.command(pass_context=True)
async def settingsclear(ctx):
	#delete the document with the guild id for the settings
	pass

bot.remove_command('help')
@bot.command(pass_context=True)
async def help(ctx, arg=""):
	commands = [
		'/help',
		'/setup',
		'/set <postingchannel/timezone/daylight/remindertime> <value>',
		'/settings [clear]',
		'/timezones',
		'/event <name> <date> [time] [description]',
		'/agenda [clear/remove] [value]'
	]
	
	descriptions = [
		"get a list of all of the commands and their descriptions",
		"set up process for the initial settings",
		"change the value of a specific setting (<parameter> is required)",
		"display all of the current settings ([parameter is optional])",
		"display all of the available timezones",
		"create a new event to store into the agenda (<parameter> is required | [parameter] is optional)",
		"display the events inside of the agenda, choose the clear the agenda, or remove an event from the agenda at a certain <position> ([parameter is optional])"
	]
	if arg != "":
		index = -1
		for i in range(len(commands)):
			if commands[i].split()[0] == "/" + arg:
				index = i
				break
		if index == -1:
			await ctx.send("That is not a valid command. Use `/help` to see the possible commands")
			return
		help_embed = discord.Embed(title=arg.capitalize(), color=0xffffff)
		help_embed.add_field(name=commands[i], value=descriptions[i], inline=False)
	else:
		help_embed = discord.Embed(title="Commands", color=0xffffff)
		s1 = ""
		s2 = ""
		for i in range(len(commands)):
			s1 += commands[i].split()[0] + "\n"
			s2 += descriptions[i] + "\n"
		help_embed.add_field(name=s1, value="Type `/help [command name]` to get more information about a command", inline=True)
	await ctx.send(embed=help_embed)

@bot.event
async def on_guild_join(guild: discord.guild):
	#print("I joined " + guild.name)
	first_ch = None
	ch = None
	for c in guild.text_channels:
			if first_ch is None:
				first_ch = c
			if str(c.name).lower() == 'general':
				ch = c
				break
	
	await (first_ch if ch is None else ch).send("Hello! Please use `/setup` to set up your agenda preferences!")

cred = credentials.Certificate(json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS']))
firebase_admin.initialize_app(cred)

db = firestore.client()

print("Firestore is now usable!")

def save_agenda(guild_id):
	agendas_doc_ref = db.collection(u'agendas').document(str(guild_id))
	this_agenda = bot_global.get_agenda(guild_id)
	agendas_doc_ref.set({
		"events_repr" : repr(this_agenda) 
		#^^ looks like [Event(datetime,title,desc),Event(datetime,title,desc)] just need to eval
	})

def load_agenda(guild_id):
	agenda_doc_ref = db.collection(u'agendas').document(str(guild_id))
	document = agenda_doc_ref.get().to_dict()
	load_events = eval(document["events_repr"])
	bot_global.set_agenda(guild_id,load_events)
	bot_global.sort_agenda(guild_id)

	# get document, evaluate the represenation of the events and then set it as the events


def save_settings(guild_id):
	settings_doc_ref = db.collection(u'settings').document(str(guild_id))
	settings_doc_ref.set({
		u'posting_channel': str(get_setting(guild_id, "posting_channel")),
		u'time_zone': str(get_setting(guild_id, "time_zone")),
		u'daylight_on': str(get_setting(guild_id, "daylight_on")),
		u'reminder_time': str(get_setting(guild_id, "reminder_time"))
	})
	
def load_settings(guild_id):
	loaded_settings = {}
	try:
		settings_doc_ref = db.collection(u'settings').document(str(guild_id))
		doc = settings_doc_ref.get().to_dict()
		loaded_settings["posting_channel"] = int(doc["posting_channel"]) if doc["posting_channel"] != "None" else None
		loaded_settings["time_zone"] = doc["time_zone"] if doc["time_zone"] != "None" else None
		loaded_settings["daylight_on"] = doc["daylight_on"] == "True"
		loaded_settings["reminder_time"] = int(doc["reminder_time"]) if doc["reminder_time"] != "None" else None
	except Exception as e:
		print(e)
		loaded_settings["posting_channel"] = loaded_settings["posting_channel"] if "posting_channel" in loaded_settings else None
		loaded_settings["time_zone"] = loaded_settings["time_zone"] if "time_zone" in loaded_settings else None
		loaded_settings["daylight_on"] = loaded_settings["daylight_on"] if "daylight_on" in loaded_settings else None
		loaded_settings["reminder_time"] = loaded_settings["reminder_time"] if "reminder_time" in loaded_settings else None

	return loaded_settings

# Keep the bot alive
keep_alive()

bot.run(os.environ['BOT_TOKEN'])