# Discord Quiz Bot

A flexible and customizable bot for hosting quiz competitions on your Discord server.

## Features

- **Quiz Creation:** Create multiple quizzes with unique names and add questions.
- **Question Management:** Add questions one by one or in bulk.
- **Quiz Flow:** Questions are displayed with a set time limit, and users answer via interactive buttons.
- **Scoring System:** Points are awarded for correct answers, and the fastest correct responder gets bonus points.
- **Leaderboard:** Displays the top scorers at the end of the quiz.
- **Excel Reporting:** Quiz results are saved into an Excel file that can be shared.
- **Advanced Settings:** Control settings like shuffling questions, auto-showing answers, and feedback messages.
- **Role-based Access:** Only users with a specified role can execute bot commands.

## Installation

### Requirements

- Python 3.8 or higher
- [discord.py](https://github.com/Rapptz/discord.py) library
- [openpyxl](https://openpyxl.readthedocs.io/en/stable/) library

### Steps

1. **Clone the Repository or Download the Files:**
   ```bash
   git clone https://github.com/your_username/discord-quiz-bot.git
   cd discord-quiz-bot
   pip install -r requirements.txt
   pip install discord.py openpyxl
	3.	Configure the Bot:
	•	Replace "BOT_TOKEN_HERE" in the code with your actual Discord bot token.
	•	Set the ALLOWED_ROLE_ID to the role ID that should have access to the commands.



Quiz Management Commands
	•	Create a Quiz:
	•	!createquiz <quiz_name>
	•	Creates a new quiz with the given name.
	•	Delete a Quiz:
	•	!deletequiz <quiz_name>
	•	Deletes the specified quiz and its Excel results file if it exists.
	•	List All Quizzes:
	•	!listquizzes
	•	Lists all created quizzes along with their total question count.
	•	Show Quiz Content:
	•	!showquiz <quiz_name>
	•	Displays all questions, options, and correct answers for the specified quiz.

Question Commands
	•	Add a Single Question:
	•	!addq or !a <quiz_name> <duration> <correct_index> Question text | Option1 | Option2 | ...
	•	Adds a single question to the specified quiz.
	•	Note: The <duration> sets the time (in seconds) for that question and <correct_index> specifies the index (starting at 0) of the correct answer.
	•	Bulk Add Questions:
	•	!bulkadd <quiz_name>
	•	Adds multiple questions at once.
	•	Each line in the message must follow the format:
duration|correct_index|Question text|Option1|Option2|...
	•	Edit an Existing Question:
	•	!editq <quiz_name> <question_number> <duration> <correct_index> Question text | Option1 | Option2 | ...
	•	Edits the question at the given 1-based index for the specified quiz.

Quiz Execution Commands
	•	Start a Quiz:
	•	!startquiz <quiz_name> [shuffle/default]
	•	Begins the quiz. If shuffle is provided (or if the quiz setting is enabled), the question options are randomized.
	•	Stop an Active Quiz:
	•	!stopquiz <quiz_name>
	•	Stops the ongoing quiz immediately.
	•	Send Quiz Results:
	•	!sendresults <quiz_name>
	•	Sends the Excel file containing the quiz results to the Discord channel.

Feedback and Settings Commands
	•	Toggle Correct Feedback (Old Command):
	•	!togglecorrect <quiz_name> <on/off>
	•	Enables or disables feedback messages for correct answers.
	•	Toggle Wrong Feedback (Old Command):
	•	!togglewrong <quiz_name> <on/off>
	•	Enables or disables feedback messages for wrong answers.
	•	Toggle Auto-Show Answer:
	•	!toggleanswer <quiz_name> <on/off>
	•	Enables or disables the auto-display of the correct answer after each question.
	•	Toggle Auto-Show Fastest Answer:
	•	!togglefastest <quiz_name> <on/off>
	•	Enables or disables the display of the fastest correct answer after each question.
	•	Set Leaderboard Settings:
	•	!setleaderboard <quiz_name> <count> <mention (true/false)>
	•	Configures the leaderboard: set the number of top scorers to display and whether to mention users or just show their names.
	•	Display Current Quiz Settings:
	•	!quizsettings
	•	Lists all current settings for each quiz including options like shuffle, auto-show, feedback, and leaderboard configuration.

Miscellaneous Commands
	•	Show Last Question’s Answer:
	•	!showanswer <quiz_name>
	•	Displays the correct answer and all available options for the last question asked.
	•	Display Fastest Correct Answer:
	•	!fastest <quiz_name>
	•	Shows the details (username and time) of the fastest correct answer for the last question.
	•	Help Menu:
	•	!helpcommand
	•	Displays this help menu with descriptions for all available commands.
	•	Ping:
	•	!ping
	•	A simple test command to check if the bot is responsive (should reply with “Pong!”).

 
