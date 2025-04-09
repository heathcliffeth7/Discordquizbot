import discord
from discord.ext import commands
import asyncio
import time
import random
from openpyxl import Workbook
import os
import io

# Only allow users with a specific role to use the commands.
ALLOWED_ROLE_ID = ROLEID  # Replace ROLEID with your actual allowed role's ID (e.g., 123456789012345678).

# Intents configuration: For message content and member info.
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Global check: Silently delete unauthorized command messages.
@bot.check
async def globally_restrict(ctx):
    if ctx.guild is None:
        return True
    if any(role.id == ALLOWED_ROLE_ID for role in ctx.author.roles):
        return True
    else:
        try:
            await ctx.message.delete()
        except Exception:
            pass
        return False

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        return
    raise error

# Global data storage:
quizzes = {}           # quizzes[quiz_name] = [question1, question2, ...]
# Each question example: {"question": str, "options": [str, ...], "correct_answer_index": int, "duration": int}
quiz_settings = {}     # quiz_settings[quiz_name] = { "shuffle": bool, "auto_show_answer": bool, "auto_show_fastest": bool, "feedback_correct": bool, "feedback_wrong": bool, "leaderboard_count": int, "leaderboard_mention": bool }
ongoing_quizzes = {}   # ongoing_quizzes[quiz_name] = bool (stop flag)
last_question_info = {}  # last_question_info[quiz_name] = { "correct_answer": str, "all_options": [str, ...], "fastest": str, "fastest_time": float }
quiz_leaderboards = {}  # quiz_leaderboards[quiz_name] = { user_id: score, ... }
all_participants = {}  # all_participants[quiz_name] = set(user_id, ...)

# --- DYNAMIC QUIZ VIEW ---
class QuizView(discord.ui.View):
    def __init__(self, question_data, total_time=20):
        super().__init__(timeout=None)
        self.question_data = question_data  # Must include "quiz_name"
        self.start_time = time.time()
        self.total_time = total_time
        self.responses = {}
        for i in range(len(question_data["options"])):
            button = discord.ui.Button(label=str(i+1), style=discord.ButtonStyle.primary)
            async def callback(interaction: discord.Interaction, index=i):
                await self.handle_answer(interaction, index)
            button.callback = callback
            self.add_item(button)

    async def handle_answer(self, interaction: discord.Interaction, answer_index: int):
        user_id = interaction.user.id
        quiz_name = self.question_data.get("quiz_name", "")
        # Update global participants list:
        if quiz_name not in all_participants:
            all_participants[quiz_name] = set()
        all_participants[quiz_name].add(user_id)
        
        if user_id in self.responses:
            await interaction.response.send_message("You have already answered this question!", ephemeral=True)
            return
        elapsed = time.time() - self.start_time
        correct = (answer_index == self.question_data["correct_answer_index"])
        self.responses[user_id] = {
            "username": interaction.user.name,
            "answer_index": answer_index,
            "correct": correct,
            "answer_time": elapsed
        }
        msg = f"You answered correctly in {elapsed:.2f} seconds!" if correct else "You answered incorrectly!"
        if correct:
            if quiz_settings.get(quiz_name, {}).get("feedback_correct", True):
                await interaction.response.send_message(msg, ephemeral=True)
        else:
            if quiz_settings.get(quiz_name, {}).get("feedback_wrong", True):
                await interaction.response.send_message(msg, ephemeral=True)

@bot.event
async def on_ready():
    print(f"Bot {bot.user} logged in.")

# !createquiz - Creates a new quiz.
@bot.command(name="createquiz")
async def create_quiz(ctx, quiz_name: str):
    if quiz_name in quizzes:
        await ctx.send(f"A quiz named **{quiz_name}** already exists.")
        return
    quizzes[quiz_name] = []
    quiz_settings[quiz_name] = {
        "shuffle": False,
        "auto_show_answer": True,
        "auto_show_fastest": True,
        "feedback_correct": True,
        "feedback_wrong": True,
        "leaderboard_count": 10,
        "leaderboard_mention": True
    }
    ongoing_quizzes[quiz_name] = False
    await ctx.send(f"Quiz **{quiz_name}** created. You can now add questions.")

# !addq (alias: !a) - Adds a single question.
@bot.command(name="addq", aliases=["a"])
async def add_question_simple(ctx, quiz_name: str, duration: int, correct_index: int, *, content: str):
    if quiz_name not in quizzes:
        await ctx.send(f"No quiz named **{quiz_name}** found. Create one using !createquiz.")
        return
    parts = [part.strip() for part in content.split("|")]
    if len(parts) < 2:
        await ctx.send("You must specify at least a question and one option.")
        return
    question_text = parts[0]
    options = parts[1:]
    if not (0 <= correct_index < len(options)):
        await ctx.send(f"Correct answer index must be between 0 and {len(options)-1}.")
        return
    quizzes[quiz_name].append({
        "question": question_text,
        "options": options,
        "correct_answer_index": correct_index,
        "duration": duration
    })
    await ctx.send(f"Question added to **{quiz_name}**. Total questions: {len(quizzes[quiz_name])}")

# !bulkadd - Bulk adds questions.
@bot.command(name="bulkadd")
async def bulk_add(ctx, quiz_name: str, *, content: str):
    if quiz_name not in quizzes:
        await ctx.send(f"No quiz named **{quiz_name}** found. Create one using !createquiz.")
        return
    lines = content.splitlines()
    added = 0
    for line in lines:
        parts = line.split("|")
        if len(parts) < 4:
            continue
        try:
            duration = int(parts[0].strip())
            correct_index = int(parts[1].strip())
        except ValueError:
            continue
        question_text = parts[2].strip()
        options = [p.strip() for p in parts[3:] if p.strip()]
        if not (0 <= correct_index < len(options)):
            continue
        quizzes[quiz_name].append({
            "question": question_text,
            "options": options,
            "correct_answer_index": correct_index,
            "duration": duration
        })
        added += 1
    await ctx.send(f"{added} questions added to **{quiz_name}**.")

# !listquizzes - Lists all existing quizzes.
@bot.command(name="listquizzes")
async def list_quizzes(ctx):
    if not quizzes:
        await ctx.send("No quizzes have been created yet.")
        return
    msg = "**Existing Quizzes:**\n"
    for qz in quizzes:
        msg += f"- {qz} (Total questions: {len(quizzes[qz])})\n"
    await ctx.send(msg)

# !deletequiz - Deletes the specified quiz and its Excel file if available.
@bot.command(name="deletequiz")
async def delete_quiz(ctx, quiz_name: str):
    if quiz_name not in quizzes:
        await ctx.send(f"No quiz named **{quiz_name}** found.")
        return
    del quizzes[quiz_name]
    if quiz_name in quiz_settings:
        del quiz_settings[quiz_name]
    if quiz_name in ongoing_quizzes:
        del ongoing_quizzes[quiz_name]
    if quiz_name in last_question_info:
        del last_question_info[quiz_name]
    if quiz_name in quiz_leaderboards:
        del quiz_leaderboards[quiz_name]
    if quiz_name in all_participants:
        del all_participants[quiz_name]
    filename = f"{quiz_name}_results.xlsx"
    if os.path.exists(filename):
        try:
            os.remove(filename)
            await ctx.send(f"Quiz **{quiz_name}** deleted and results file `{filename}` removed.")
        except Exception as e:
            await ctx.send(f"Quiz deleted but error occurred while deleting Excel file: {e}")
    else:
        await ctx.send(f"Quiz **{quiz_name}** deleted. (No Excel file found.)")

# !editq - Edits an existing question (question_index is 1-based).
@bot.command(name="editq")
async def edit_question(ctx, quiz_name: str, question_index: int, duration: int, correct_index: int, *, content: str):
    if quiz_name not in quizzes:
        await ctx.send(f"No quiz named **{quiz_name}** found.")
        return
    idx = question_index - 1
    if idx < 0 or idx >= len(quizzes[quiz_name]):
        await ctx.send("Invalid question index.")
        return
    parts = [part.strip() for part in content.split("|")]
    if len(parts) < 2:
        await ctx.send("You must provide at least a question text and one option.")
        return
    question_text = parts[0]
    options = parts[1:]
    if not (0 <= correct_index < len(options)):
        await ctx.send(f"Correct answer index must be between 0 and {len(options)-1}.")
        return
    quizzes[quiz_name][idx] = {
        "question": question_text,
        "options": options,
        "correct_answer_index": correct_index,
        "duration": duration
    }
    await ctx.send(f"Question {question_index} in **{quiz_name}** updated.")

# !mixquestions - Sets the shuffle mode for the quiz.
@bot.command(name="mixquestions")
async def set_shuffle(ctx, quiz_name: str, mode: str):
    if quiz_name not in quizzes:
        await ctx.send(f"No quiz named **{quiz_name}** found.")
        return
    state = mode.lower() in ["true", "yes", "1", "shuffle"]
    if quiz_name not in quiz_settings:
        quiz_settings[quiz_name] = {}
    quiz_settings[quiz_name]["shuffle"] = state
    await ctx.send(f"Shuffle mode for **{quiz_name}** set to {'active' if state else 'inactive'}.")

# !togglecorrect - Enables/disables correct feedback messages.
@bot.command(name="togglecorrect")
async def toggle_correct(ctx, quiz_name: str, mode: str):
    if quiz_name not in quiz_settings:
        await ctx.send(f"No quiz named **{quiz_name}** found.")
        return
    state = mode.lower() in ["on", "true", "1"]
    quiz_settings[quiz_name]["feedback_correct"] = state
    await ctx.send(f"'Correct answer' feedback for **{quiz_name}** will be {'shown' if state else 'hidden'}.")

# !togglewrong - Enables/disables incorrect feedback messages.
@bot.command(name="togglewrong")
async def toggle_wrong(ctx, quiz_name: str, mode: str):
    if quiz_name not in quiz_settings:
        await ctx.send(f"No quiz named **{quiz_name}** found.")
        return
    state = mode.lower() in ["on", "true", "1"]
    quiz_settings[quiz_name]["feedback_wrong"] = state
    await ctx.send(f"'Incorrect answer' feedback for **{quiz_name}** will be {'shown' if state else 'hidden'}.")

# !toggleanswer - Enables/disables auto-show correct answer.
@bot.command(name="toggleanswer")
async def toggle_answer_cmd(ctx, quiz_name: str, mode: str):
    if quiz_name not in quiz_settings:
        await ctx.send(f"No quiz named **{quiz_name}** found.")
        return
    state = mode.lower() in ["on", "true", "1"]
    quiz_settings[quiz_name]["auto_show_answer"] = state
    await ctx.send(f"Auto-show correct answer for **{quiz_name}** is now {'enabled' if state else 'disabled'}.")

# !togglefastest - Enables/disables auto-show fastest correct answer.
@bot.command(name="togglefastest")
async def toggle_fastest(ctx, quiz_name: str, mode: str):
    if quiz_name not in quiz_settings:
        await ctx.send(f"No quiz named **{quiz_name}** found.")
        return
    state = mode.lower() in ["on", "true", "1"]
    quiz_settings[quiz_name]["auto_show_fastest"] = state
    await ctx.send(f"Auto-show fastest answer for **{quiz_name}** is now {'enabled' if state else 'disabled'}.")

# !setleaderboard - Sets the leaderboard settings.
@bot.command(name="setleaderboard")
async def set_leaderboard(ctx, quiz_name: str, count: int, mention: str):
    if quiz_name not in quiz_settings:
        await ctx.send(f"No quiz named **{quiz_name}** found.")
        return
    try:
        count = int(count)
    except ValueError:
        await ctx.send("Count must be a number.")
        return
    mention_bool = mention.lower() in ["true", "yes", "1", "mention"]
    quiz_settings[quiz_name]["leaderboard_count"] = count
    quiz_settings[quiz_name]["leaderboard_mention"] = mention_bool
    await ctx.send(f"Leaderboard settings for **{quiz_name}** updated: Top {count} and will be shown as {'mentions' if mention_bool else 'names only'}.")

# !stopquiz - Stops the active quiz.
@bot.command(name="stopquiz")
async def stop_quiz(ctx, quiz_name: str):
    if quiz_name not in ongoing_quizzes:
        await ctx.send(f"No active quiz named **{quiz_name}** found.")
        return
    ongoing_quizzes[quiz_name] = True
    await ctx.send(f"Quiz **{quiz_name}** is being stopped...")

# !startquiz - Starts the quiz.
@bot.command(name="startquiz")
async def start_quiz(ctx, quiz_name: str, shuffle: str = "default"):
    if quiz_name not in quizzes:
        await ctx.send(f"No quiz named **{quiz_name}** found.")
        return
    question_list = quizzes[quiz_name]
    if not question_list:
        await ctx.send(f"**{quiz_name}** has no questions. Please add some.")
        return

    ongoing_quizzes[quiz_name] = False

    if shuffle.lower() == "default":
        shuffle_flag = quiz_settings.get(quiz_name, {}).get("shuffle", False)
    else:
        shuffle_flag = shuffle.lower() in ["true", "shuffle", "yes", "1"]

    total_scores = {}
    all_participants[quiz_name] = set()

    for idx, qdata in enumerate(question_list, start=1):
        if ongoing_quizzes.get(quiz_name, False):
            await ctx.send(f"Quiz **{quiz_name}** was stopped by a user.")
            break

        question_text = qdata["question"]
        orig_options = qdata["options"]
        if shuffle_flag:
            original_correct = orig_options[qdata["correct_answer_index"]]
            shuffled_options = orig_options.copy()
            random.shuffle(shuffled_options)
            new_correct_index = shuffled_options.index(original_correct)
        else:
            shuffled_options = orig_options
            new_correct_index = qdata["correct_answer_index"]

        total_time = qdata.get("duration", 20)
        display_question = {
            "question": question_text,
            "options": shuffled_options,
            "correct_answer_index": new_correct_index,
            "quiz_name": quiz_name
        }
        embed = discord.Embed(
            title=f"{quiz_name} - Question {idx}",
            description=question_text,
            color=discord.Color.blue()
        )
        for i, opt in enumerate(shuffled_options, start=1):
            embed.add_field(name=f"Option {i}", value=opt, inline=False)
        embed.set_footer(text=f"Time remaining: {total_time} seconds")

        view = QuizView(display_question, total_time=total_time)
        quiz_message = await ctx.send(embed=embed, view=view)

        for remaining in range(total_time, 0, -1):
            if ongoing_quizzes.get(quiz_name, False):
                break
            embed.set_footer(text=f"Time remaining: {remaining} seconds")
            await quiz_message.edit(embed=embed, view=view)
            await asyncio.sleep(1)
        for child in view.children:
            child.disabled = True
        await quiz_message.edit(view=view)

        correct_responses = [(uid, data) for uid, data in view.responses.items() if data["correct"]]
        correct_responses.sort(key=lambda x: x[1]["answer_time"])
        base_score = 1000
        score_step = 100
        for rank, (uid, data) in enumerate(correct_responses, start=1):
            score_award = base_score - (rank - 1) * score_step
            if score_award < 0:
                score_award = 0
            total_scores[uid] = total_scores.get(uid, 0) + score_award

        if correct_responses:
            fastest_user_id, fastest_data = correct_responses[0]
            fastest_user_name = fastest_data["username"]
            fastest_time = fastest_data["answer_time"]
        else:
            fastest_user_name = None
            fastest_time = None
        last_question_info[quiz_name] = {
            "correct_answer": shuffled_options[new_correct_index],
            "all_options": shuffled_options,
            "fastest": fastest_user_name,
            "fastest_time": fastest_time
        }

        if quiz_settings.get(quiz_name, {}).get("auto_show_answer", True):
            await ctx.send(f"Correct answer: **{shuffled_options[new_correct_index]}**")
        if quiz_settings.get(quiz_name, {}).get("auto_show_fastest", True):
            if correct_responses:
                await ctx.send(f"Fastest correct answer: **{fastest_user_name}** ({fastest_time:.2f} sec)")
            else:
                await ctx.send("No one answered correctly for this question.")
        await asyncio.sleep(3)

    await ctx.send("Quiz completed. Thank you for participating!")
    
    participants = all_participants.get(quiz_name, set())
    for uid in participants:
        if uid not in total_scores:
            total_scores[uid] = 0

    quiz_leaderboards[quiz_name] = total_scores
    if total_scores:
        wb = Workbook()
        ws = wb.active
        ws.title = "Quiz Results"
        ws.append(["User ID", "Username", "Score"])
        sorted_total = sorted(total_scores.items(), key=lambda x: x[1], reverse=True)
        for user_id, score in sorted_total:
            member = ctx.guild.get_member(user_id)
            username = member.name if member else f"Unknown({user_id})"
            ws.append([str(user_id), username, score])
        filename = f"{quiz_name}_results.xlsx"
        wb.save(filename)

# !sendresults - Sends the quiz's Excel results file to Discord.
@bot.command(name="sendresults")
async def send_results(ctx, quiz_name: str):
    filename = f"{quiz_name}_results.xlsx"
    if os.path.exists(filename):
        await ctx.send(file=discord.File(filename))
    else:
        await ctx.send(f"No Excel file found for quiz **{quiz_name}**.")

# !showanswer - Shows the correct answer and options for the last question.
@bot.command(name="showanswer")
async def show_answer(ctx, quiz_name: str):
    if quiz_name not in last_question_info:
        await ctx.send("No information found for the last question of this quiz.")
        return
    info = last_question_info[quiz_name]
    options_str = ", ".join(info["all_options"])
    await ctx.send(f"Correct answer: **{info['correct_answer']}**\nOptions: {options_str}")

# !fastest - Shows the fastest correct answer details for the last question.
@bot.command(name="fastest")
async def fastest_answer(ctx, quiz_name: str):
    if quiz_name not in last_question_info:
        await ctx.send("No information found for the last question of this quiz.")
        return
    info = last_question_info[quiz_name]
    if info.get("fastest") is None:
        await ctx.send("No one answered correctly for this question.")
        return
    await ctx.send(f"Fastest correct answer: **{info['fastest']}** ({info['fastest_time']:.2f} sec)")

# !showquiz - Lists all questions and correct answers of the quiz.
@bot.command(name="showquiz")
async def show_quiz(ctx, quiz_name: str):
    if quiz_name not in quizzes:
        await ctx.send(f"No quiz named **{quiz_name}** found.")
        return
    msg = f"**{quiz_name}** Quiz Content:\n"
    for i, q in enumerate(quizzes[quiz_name], start=1):
        correct = q["options"][q["correct_answer_index"]]
        options = " | ".join(q["options"])
        msg += f"{i}. {q['question']}\nOptions: {options}\nCorrect answer: **{correct}**\n\n"
    await ctx.send(msg)

# !leaderboard - Shows the leaderboard (top entries) for the quiz.
@bot.command(name="leaderboard")
async def leaderboard(ctx, quiz_name: str):
    if quiz_name not in quiz_leaderboards:
        await ctx.send(f"No leaderboard found for quiz **{quiz_name}**. The quiz might not be completed yet.")
        return
    scores = quiz_leaderboards[quiz_name]
    if not scores:
        await ctx.send("No participants scored any points in this quiz.")
        return
    lb_count = quiz_settings.get(quiz_name, {}).get("leaderboard_count", 10)
    lb_mention = quiz_settings.get(quiz_name, {}).get("leaderboard_mention", True)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:lb_count]
    msg = f"**{quiz_name}** Leaderboard (Top {lb_count}):\n"
    for rank, (user_id, score) in enumerate(sorted_scores, start=1):
        member = ctx.guild.get_member(user_id)
        user_str = member.mention if (member and lb_mention) else (member.name if member else f"Unknown({user_id})")
        msg += f"{rank}. {user_str} - {score} points\n"
    await ctx.send(msg)

# !quizsettings - Lists the settings for all quizzes.
@bot.command(name="quizsettings")
async def quiz_settings_cmd(ctx):
    if not quizzes:
        await ctx.send("No quizzes have been created yet.")
        return
    embed = discord.Embed(
        title="Quiz Settings",
        description="Current settings for all quizzes:",
        color=discord.Color.purple()
    )
    for quiz_name in quizzes:
        settings = quiz_settings.get(quiz_name, {})
        shuffle_status = settings.get("shuffle", False)
        auto_show_answer = settings.get("auto_show_answer", True)
        auto_show_fastest = settings.get("auto_show_fastest", True)
        feedback_correct = settings.get("feedback_correct", True)
        feedback_wrong = settings.get("feedback_wrong", True)
        lb_count = settings.get("leaderboard_count", 10)
        lb_mention = settings.get("leaderboard_mention", True)
        ongoing_status = ongoing_quizzes.get(quiz_name, False)
        question_count = len(quizzes[quiz_name])
        embed.add_field(
            name=quiz_name,
            value=(
                f"**Total Questions:** {question_count}\n"
                f"**Shuffle:** {'Enabled' if shuffle_status else 'Disabled'}\n"
                f"**Auto-show Correct Answer:** {'Enabled' if auto_show_answer else 'Disabled'}\n"
                f"**Auto-show Fastest Answer:** {'Enabled' if auto_show_fastest else 'Disabled'}\n"
                f"**Feedback - Correct Message:** {'Enabled' if feedback_correct else 'Disabled'}\n"
                f"**Feedback - Incorrect Message:** {'Enabled' if feedback_wrong else 'Disabled'}\n"
                f"**Leaderboard:** Top {lb_count}, {'Mentions' if lb_mention else 'Names only'}\n"
                f"**Active Quiz:** {'Yes' if ongoing_status else 'No'}"
            ),
            inline=False
        )
    await ctx.send(embed=embed)

# !quizidlist - Lists participant IDs for the specified quiz in a TXT file.
@bot.command(name="quizidlist")
async def quiz_id_list(ctx, quiz_name: str):
    if quiz_name not in all_participants or not all_participants[quiz_name]:
        await ctx.send(f"No participants found for quiz **{quiz_name}**.")
        return
    id_list = list(all_participants[quiz_name])
    id_list.sort()
    lines = []
    for i in range(0, len(id_list), 150):
        group = id_list[i:i+150]
        line = " ".join(str(user_id) for user_id in group)
        lines.append(line)
    text = "\n".join(lines)
    file_object = io.StringIO(text)
    file_object.name = f"quizidlist_{quiz_name}.txt"
    await ctx.send(file=discord.File(file_object))
    file_object.close()

# !quizhelp - Displays the help menu with all commands.
@bot.command(name="quizhelp")
async def quiz_help(ctx):
    help_text = (
        "Quiz Bot Help Menu\n"
        "You can create a quiz, add questions, edit questions, stop a quiz, run the quiz, send the results as an Excel file (only via !sendresults), and view information about the last question.\n\n"
        "Additional Features:\n"
        "!toggleanswer <quiz_name> <on/off>: Enable/disable auto-show of the correct answer after each question.\n"
        "!togglefastest <quiz_name> <on/off>: Enable/disable auto-show of the fastest correct answer after each question.\n"
        "!togglecorrect <quiz_name> <on/off>: (Old toggle) Enable/disable correct feedback messages.\n"
        "!togglewrong <quiz_name> <on/off>: (Old toggle) Enable/disable incorrect feedback messages.\n"
        "!setleaderboard <quiz_name> <count> <mention (true/false)>: Set leaderboard settings.\n"
        "!showquiz <quiz_name>: List all questions and correct answers of the quiz.\n"
        "!leaderboard <quiz_name>: Show the leaderboard (top entries) for the quiz.\n\n"
        "!createquiz <quiz_name>\n"
        "Creates a new quiz.\n"
        "!addq (alias: !a) <quiz_name> <duration> <correct_index> Question text | Option1 | Option2 | ...\n"
        "Simplified command to add a single question.\n"
        "!editq <quiz_name> <question_index> <duration> <correct_index> Question text | Option1 | Option2 | ...\n"
        "Edits the specified question (question_index is 1-based).\n"
        "!bulkadd <quiz_name>\n"
        "Bulk add questions. Each line should be in the format: duration|correct_index|Question text|Option1|Option2|...\n"
        "Example (for 10 questions):\n"
        "!bulkadd <quizname>\n"
        "30|1|What is L1?|Option A|Option B|Option C\n"
        "20|0|Favorite color?|Blue|Red|Green|Yellow\n"
        "25|2|Which planet is known as the Red Planet?|Earth|Venus|Mars\n"
        "30|1|Capital of Turkey?|Istanbul|Ankara|Izmir\n"
        "20|0|What is 2+2?|3|4|5\n"
        "30|2|Which language is used for Android development?|Java|Kotlin|Swift|Python\n"
        "25|0|Who painted the Mona Lisa?|Da Vinci|Picasso|Van Gogh\n"
        "30|1|Chemical symbol for Gold?|Au|Ag|Pt\n"
        "20|2|Largest ocean on Earth?|Atlantic|Indian|Pacific\n"
        "30|0|Currency of Japan?|Yen|Dollar|Euro\n\n"
        "!listquizzes: List all existing quizzes and their question counts.\n"
        "!deletequiz <quiz_name>: Delete the specified quiz and its Excel file if available.\n"
        "!mixquestions <quiz_name> <true/false>: Set shuffle mode for the quiz.\n"
        "!toggleanswer <quiz_name> <on/off>: Enable/disable auto-show of the correct answer after each question.\n"
        "!togglefastest <quiz_name> <on/off>: Enable/disable auto-show of the fastest correct answer after each question.\n"
        "!togglecorrect <quiz_name> <on/off>: (Old toggle) Enable/disable correct feedback messages.\n"
        "!togglewrong <quiz_name> <on/off>: (Old toggle) Enable/disable incorrect feedback messages.\n"
        "!setleaderboard <quiz_name> <count> <mention (true/false)>: Set leaderboard settings.\n"
        "!stopquiz <quiz_name>: Stop the active quiz.\n"
        "!startquiz <quiz_name> [shuffle/default]: Start the quiz. If 'default' is used, the preset shuffle mode is applied. Only a thank you message is sent when the quiz finishes.\n"
        "!sendresults <quiz_name>: Send the quiz's Excel results file to Discord.\n"
        "!showanswer <quiz_name>: Show the correct answer and all options for the last question.\n"
        "!fastest <quiz_name>: Show the fastest correct answer details for the last question.\n"
        "!showquiz <quiz_name>: List all questions and correct answers of the quiz.\n"
        "!leaderboard <quiz_name>: Show the leaderboard (top entries) for the quiz.\n"
        "!quizsettings: List the settings for all quizzes.\n"
        "!quizidlist <quiz_name>: List participant IDs (every 150 IDs on a new line) in a TXT file.\n"
        "!quizhelp - Show this help menu.\n"
        "!ping - Test command, replies with 'Pong!'."
    )
    if len(help_text) <= 2000:
        await ctx.send(help_text)
    else:
        for i in range(0, len(help_text), 2000):
            await ctx.send(help_text[i:i+2000])

# !ping - Test command.
@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong!")

bot.run("BOT_TOKEN_HERE")
