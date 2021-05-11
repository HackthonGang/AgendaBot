# AgendaBot
RUHacks 2021 entry. This is a bot for teams to schedule their events so they will not miss out on anything!

## Inspiration
Having been through countless group projects and hackathons together, our team members realized that it was hard to keep track of a good schedule that everyone can commit to with merely our human brains. 

This where we come up with the idea to build a **discord bot** that lives within a server where everyone can share one schedule together!

## What it does
* Customizable settings (Timezone, Text Channel for reminders. Daylight savings, Reminder time (eg. 15 minutes before event ) )
* Creates event & adds to the agenda
* Alerts group members when an event approaches (Customizable)
* List of events available for all members at all times (One command away!)
* Automatically saves the settings & agenda for the server within **Google Firebase (Cloud Firestore)**

## How we built it
* With the help of Python and discord.py, we were able to write multiple commands available for the users to either create, edit or customize the agenda & settings.
* In terms of storing the data for agenda & settings, we connected our codebase to **Google Firebase**. We stored all servers' settings and agendas in two different collections. (JSON format)
* Each guild/server has its own document in each collection (settings or agenda). The data for each server is differentiated by their guild ID.

## Challenges we ran into
* **Timezone:** We tried using the region property that each guild has, but we ended up realizing that the information is not helpful. (Region was not specific enough. Ex. Brazil region has 3 different timezones)
* **Database:** The database was pretty challenging to set up, but we managed to read through the API documentation more thoroughly and successfully established the connection!
* **Embed Formation:** It was quite difficult for us to format the Embed content, so they appear to be in the format of rows and columns.

## Accomplishments that we're proud of
* For some of us, it was our first time working with **discord.py** or **Google Firebase**. We are proud that we worked through our project pretty smoothly.
* Learning how to deal with date and time such that we are able to send out reminders at an accurate time. And of course, dealing with timezones and daylight savings.

## What's next for Agenda Bot
* Direct Message the Agenda Bot
* Optimize Google Firebase read & write to manage larger traffic
* Add more functionalities/commands
* Host our **discord bot**
