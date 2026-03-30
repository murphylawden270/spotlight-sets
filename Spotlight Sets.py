import discord # source: https://youtu.be/CHbN_gB30Tw?list=PL-7Dfw57ZZVQ-GCNQS4Kyz637Fffhb0Hs + https://youtu.be/0lhYddc5M9w?list=PL-7Dfw57ZZVQ-GCNQS4Kyz637Fffhb0Hs
from discord.ext import commands # source: https://youtu.be/26Sj5hJFqUs?list=PL-7Dfw57ZZVQ-GCNQS4Kyz637Fffhb0Hs
from discord import app_commands
from discord.ui import Button, View # source: https://youtu.be/RCPPqPdlvE8?si=G-VJxD0UOjm-gsO0
from supabase import create_client
import asyncio
import re
import io
from dotenv import load_dotenv
import os
from datetime import datetime, timezone

# Self note: discord.py works with aync functions but create_client is sync. acreate_client gives network, so didn't wanna risk it. So call using create_client, then force it to async by wrapping it with asyncio.to_thread.

# source: https://youtu.be/sOwG0bw0RNU?si=0Ty_koXKlg21pSSk
load_dotenv(r"C:\Users\User\OneDrive\Desktop\Spotlight Sets\imp.env")
token = os.getenv("token")
url = os.getenv("url")
key = os.getenv("key")
socmed_server = int(os.getenv("socmed_server"))
spotlights_id = int(os.getenv("spotlights_id"))
spotlights_set_id = int(os.getenv("spotlights_set_id"))
spotlight_staff = int(os.getenv("spotlight_staff"))
reaction = os.getenv("reaction")
reaction_id = int(os.getenv("reaction_id"))

# regx pattern for different parts of spotlight message
spotlight_message = "^.+ by .+\n?```[\s\S]+```$"
spotlight_sets = "```([\s\S]+?)```"
individual_set = "\n\s*\n"
set_format = "(^.+) by"
set_suggester = "by (.+)\n?```"
pokemon = "^(.+?)\s*@"

# bot message id for raw_reaction, raw_edit, raw_delete
async def bot_message_id(message_id):
    try:
        lappland = create_client(url, key)
        meow = lappland.table("spotlight_set_message_id").select("bot_message_id").eq("user_message_id", message_id)
        id = await asyncio.to_thread(meow.execute)
        if not id.data:
            return None
        return id.data[0]["bot_message_id"]
    except Exception as e:
        print(f'ERROR in bot_message_id: {e}')

async def get_month():
    try:
        lappland = create_client(url, key)
        meow = lappland.table("spotlight_month").select("spotlight_month").eq("active", True)
        month = await asyncio.to_thread(meow.execute)
        if not month.data:
            return None
        return month.data[0]["spotlight_month"]
    except Exception as e:
        print(f'ERROR in get_month: {e}')

def spotlight_reaction(message, reaction, reaction_id):
    return any(
        r.emoji.name == reaction and r.emoji.id == reaction_id
        for r in message.reactions
    )

def staff_role(member):
    return any(role.id == spotlight_staff for role in member.roles)

class Client(commands.Bot):

    async def on_ready(self):
        print(f'logged in as {self.user}!')

        try:
            synced = await self.tree.sync(guild=discord.Object(id=socmed_server))
            print(f'Synced {len(synced)} commands to server {socmed_server}')
        except Exception as e:
            print(f'ERROR: {e}')
            pass       

        server = self.get_guild(socmed_server)
        spotlights_set = self.get_channel(spotlights_set_id)
        spotlights = self.get_channel(spotlights_id)
        sent_date = datetime(2026, 4, 1, tzinfo=timezone.utc) # messages before April 1st go to old_spotlight_set_message_id, newer to spotlight_set_message_id

        if not server or not spotlights_set:
            return

        self.spotlights_set = self.get_channel(spotlights_set_id)

        start_1 = await spotlights.send("**Spotlight Bot Is Online!**")
        start_2 = await spotlights.send("**Fetching Messages...**")

        async def yes_callback(interaction):
            await interaction.response.defer() 
            if not staff_role(interaction):
                await interaction.followup.send("**You don't have permission.**", ephemeral=True)
                return
            
            lappland = create_client(url, key)
            button.stop()
            reply_1 = await interaction.followup.send("**Implementing changes...**")
            messages = [message async for message in spotlights.history(limit=None)]
            messages.reverse()

            for message in messages:
                if not spotlight_reaction(message, reaction, reaction_id):
                    continue

                if not re.search(spotlight_message, message.content):
                    continue

                if message.created_at < sent_date:
                    select_table = "old_spotlight_set_message_id"
                else:
                    select_table = "spotlight_set_message_id"

                existing_id = lappland.table(select_table).select("*").eq("user_message_id", message.id)
                meow = await asyncio.to_thread(existing_id.execute)

                if not meow.data:
                    if select_table == "spotlight_set_message_id":
                        content = await spotlights_set.send(message.content)
                        stored_message = lappland.table(select_table).insert({
                            "user_message_id": message.id,
                            "bot_message_id": content.id,
                            "spotlight_context": message.content
                        })
                    else:
                        stored_message = lappland.table(select_table).insert({
                            "user_message_id": message.id,
                            "bot_message_id": content.id,
                            "spotlight_context": message.content
                        })
                    await asyncio.to_thread(stored_message.execute)
                    await asyncio.sleep(5)

                else:
                    try:
                        bot_id = meow.data[0]["bot_message_id"]
                        existing_in_db = meow.data[0]["spotlight_context"]
                        if existing_in_db != message.content:
                            try:
                                bot_edit = await spotlights_set.fetch_message(bot_id)
                                await bot_edit.edit(content=message.content)
                                edited_message = lappland.table(select_table).update({
                                    "last_edit": datetime.now(timezone.utc).isoformat(),
                                    "spotlight_context": message.content,
                                }).eq("user_message_id", message.id)
                                await asyncio.to_thread(edited_message.execute)
                            except discord.NotFound:
                                pass
                            except discord.Forbidden:
                                pass 
                        else:
                            await asyncio.sleep(5)
                    except discord.NotFound:
                        pass
                        await asyncio.sleep(5)

            reacted_message_ids = [
                str(message.id) for message in messages
                if spotlight_reaction(message, reaction, reaction_id) and re.search(spotlight_message, message.content)
                ]

            meow = lappland.table("spotlight_set_message_id").select("user_message_id")
            existing_user_message_ids = await asyncio.to_thread(meow.execute)

            for message_id in existing_user_message_ids.data:
                    if str(message_id["user_message_id"]) not in reacted_message_ids:
                        try:
                            bot_id = await bot_message_id(message_id["user_message_id"])
                            bot_delete = await spotlights_set.fetch_message(bot_id)
                            await bot_delete.delete()
                            deleted_message = lappland.table("spotlight_set_message_id").delete(
                            ).eq("user_message_id", message_id["user_message_id"])
                            await asyncio.to_thread(deleted_message.execute)
                            await asyncio.sleep(5)
                        except discord.NotFound:
                            pass

            reply_2 = await spotlights.send("**Changes Implemented!**")
            await reply_1.delete()
            await spotlights.delete_messages([start_1, start_2, start_3])

        async def no_callback(interaction):
            await interaction.response.defer()
            if not staff_role(interaction):
                await interaction.followup.send("**You don't have permission.**", ephemeral=True)
                return
            button.stop()
            reply_3 = await interaction.followup.send("**Changes will not be implemented.**")
            await asyncio.sleep(2)
            await reply_3.delete()
            await spotlights.delete_messages([start_1, start_2, start_3])

        Yes = Button(label="Yes", style=discord.ButtonStyle.green)
        No = Button(label="No", style=discord.ButtonStyle.red)

        Yes.callback = yes_callback
        No.callback = no_callback

        button = View()
        button.add_item(Yes)
        button.add_item(No)
        start_3 = await spotlights.send("*Do you wish to implement older changes?*",view=button)

    # so apparently I need raw events to get the bot to catch older messages that are not stored in the bot's cache but it only gets the ID, but thats all I need
    # https://discordpy.readthedocs.io/en/stable/api.html#discord.RawMessageUpdateEvent 
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):

        if payload.emoji.name != reaction or payload.emoji.id != reaction_id: # checking coorect reaction
            return

        if payload.guild_id is None or payload.guild_id != socmed_server or payload.channel_id != spotlights_id: # checking correct channel
            return

        server = self.get_guild(payload.guild_id)
        member = server.get_member(payload.user_id)

        if member is None or member.bot: 
            return

        if not staff_role(member):
            return

        channel = self.get_channel(payload.channel_id)
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        if not re.search(spotlight_message, message.content):
            return

        lappland = create_client(url, key)
        month = await get_month()

        meow = lappland.table("spotlight_set_message_id").select("*").eq("user_message_id", message.id)
        existing_id = await asyncio.to_thread(meow.execute)
        if existing_id.data:
            return

        spotlights_set = self.get_channel(spotlights_set_id)
        store = await spotlights_set.send(message.content)
        inserted_message = lappland.table("spotlight_set_message_id").insert({
            "user_message_id": message.id,
            "bot_message_id": store.id,
            "spotlight_context": message.content,
            "spotlight_month": month
        })
        await asyncio.to_thread(inserted_message.execute)
 
        # this shit breaks the sets and storing in db
        set_blocks = re.findall(spotlight_sets, message.content)

        if len(set_blocks) == 1:
            sets = re.split(individual_set, set_blocks[0].strip())
        else:
            sets = [block.strip() for block in set_blocks]

        sets = ["\n".join(line.strip() for line in set.strip().splitlines()) for set in sets]

        format = re.findall(set_format, message.content)[0]

        suggester_match = re.search(set_suggester, message.content)
        if suggester_match:
            suggesters = [suggester.strip() for suggester in suggester_match.group(1).split(" and ")]
        else:
            suggesters = ["NA"]

        if len(suggesters) == len(sets):
            pairs = list(zip(sets, suggesters))
        elif len(suggesters) == 1:
            pairs = [(set, suggesters[0]) for set in sets]
        else:
            pairs = [(set, "NA") for set in sets]

        for set, suggester in pairs:
            insert_set = lappland.table("spotlight_set").insert({
                "user_message_id": message.id,
                "format": format,
                "set": set,
                "suggested_by": suggester,
                "spotlight_month": month
            })
            await asyncio.to_thread(insert_set.execute)

    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
            if payload.guild_id is None or payload.guild_id != socmed_server or payload.channel_id != spotlights_id:
                return
            
            content = payload.data.get("content", "")
            if not re.search(spotlight_message, content):
                return

            channel = self.get_channel(payload.channel_id)
            try:
                after = await channel.fetch_message(payload.message_id)
            except discord.NotFound:
                return

            if after.author == self.user:
                return
            
            if not re.search(spotlight_message, after.content): 
                return
            
            spotlights_set = self.get_channel(spotlights_set_id)
            bot_id = await bot_message_id(payload.message_id)
            
            if bot_id is None:  
                return
            
            bot_edit = await spotlights_set.fetch_message(bot_id)

            lappland = create_client(url, key)
            month = await get_month()
            await bot_edit.edit(content=after.content)
            message_update =  lappland.table("spotlight_set_message_id").update({
                "last_edit" : datetime.now(timezone.utc).isoformat(),
                "spotlight_context": after.content,
            }).eq("user_message_id", payload.message_id)
            await asyncio.to_thread(message_update.execute)

            delete_old_set = lappland.table("spotlight_set").delete(
            ).eq("user_message_id", payload.message_id)
            await asyncio.to_thread(delete_old_set.execute)
            
            set = re.findall(spotlight_sets, after.content)[0]
            sets = re.split(individual_set, set)

            format = re.findall(set_format, after.content)[0]

            suggester_match = re.search(set_suggester, after.content)
            if suggester_match:
                suggesters = [suggester.strip() for suggester in suggester_match.group(1).split(" and ")]
            else:
                suggesters = ["NA"]

            if len(suggesters) == len(sets):
                pairs = list(zip(sets, suggesters))  # zip is used to merge 2 lists and make it a set 
            elif len(suggesters) == 1:
                pairs = [(set, suggesters[0]) for set in sets]
            else:
                pairs = [(set, "NA") for set in sets]


            for set, suggester in pairs:
                insert_set = lappland.table("spotlight_set").insert({
                "user_message_id": payload.message_id,
                "format": format,
                "set": set,
                "suggested_by": suggester,
                "spotlight_month": month
                })
                await asyncio.to_thread(insert_set.execute)
            
    async def on_raw_message_delete(self, payload: discord.RawMessageUpdateEvent):
        if payload.guild_id is None or payload.guild_id != socmed_server or payload.channel_id != spotlights_id:
            return
        
        if payload.cached_message and payload.cached_message.author == self.user:
            return  
        
        spotlights_set = self.get_channel(spotlights_set_id)
        bot_id = await bot_message_id(payload.message_id)
        if bot_id is None:
            return

        try:
            bot_delete = await spotlights_set.fetch_message(bot_id)
        except discord.NotFound:
            return
                    
        channel = self.get_channel(spotlights_id)

        Yes = Button(label="Yes", style=discord.ButtonStyle.green)
        No = Button(label="No", style=discord.ButtonStyle.red)

        async def yes_callback(interaction):
            await interaction.response.defer()
            if not staff_role(interaction.user):
                await interaction.followup.send("**You don't have permission.**", ephemeral=True)
                return
            
            try:
                lappland = create_client(url, key)
                message_id = lappland.table("spotlight_set_message_id").select("user_message_id").eq("bot_message_id", bot_id)
                meow = await asyncio.to_thread(message_id.execute)
                if meow.data:
                    user_msg_id = meow.data[0]["user_message_id"]
                    deleted_message = lappland.table("spotlight_set_message_id").delete().eq("user_message_id", user_msg_id)
                    await asyncio.to_thread(deleted_message.execute)
                
                await bot_delete.delete()
                reply = await interaction.followup.send("**Message Deleted!**")
                await asyncio.sleep(2)
                await reply.delete()
            except Exception:
                pass

        async def no_callback(interaction):
            await interaction.response.defer()
            if not staff_role(interaction.user):
                await interaction.followup.send("**You don't have permission.**", ephemeral=True)
                return
            button.stop()
            reply = await interaction.followup.send("*Message will not be deleted.*")
            await asyncio.sleep(2)
            await reply.delete()

        Yes.callback = yes_callback
        No.callback = no_callback

        button = View()
        button.add_item(Yes)
        button.add_item(No)
        prompt = await channel.send("**Do you wish to delete this message?**",view=button)
            
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = Client(command_prefix="/", intents=intents)

@bot.tree.command(name="start_set_collection", description="start collecting sets for the month", guild=discord.Object(id=socmed_server))
@app_commands.describe(month = "the month for which to collect sets")
@app_commands.choices(month =[
    app_commands.Choice(name="January", value="January"),
    app_commands.Choice(name="February", value="February"),
    app_commands.Choice(name="March", value="March"),
    app_commands.Choice(name="April", value="April"),
    app_commands.Choice(name="May", value="May"),
    app_commands.Choice(name="June", value="June"),
    app_commands.Choice(name="July", value="July"),
    app_commands.Choice(name="August", value="August"),
    app_commands.Choice(name="September", value="September"),
    app_commands.Choice(name="October", value="October"),
    app_commands.Choice(name="November", value="November"),
    app_commands.Choice(name="December", value="December")
])
@app_commands.describe(year = "the year for which to collect sets")
@app_commands.choices(year =[
    app_commands.Choice(name="2026", value="2026"),
    app_commands.Choice(name="2027", value="2027"),
    app_commands.Choice(name="2028", value="2028"),
    app_commands.Choice(name="2029", value="2029"),
    app_commands.Choice(name="2030", value="2030")
])
async def start_set_collection(interaction: discord.Interaction, month: app_commands.Choice[str], year: app_commands.Choice[str]):
    await interaction.response.defer()
    if not staff_role(interaction):
        await interaction.followup.send("**You don't have permission.**", ephemeral=True)
        return
    lappland = create_client(url, key)
    channel = bot.get_channel(spotlights_id)
    meow = lappland.table("spotlight_month").select("*").eq("spotlight_month", f"{month.value} {year.value}")
    month_exists = await asyncio.to_thread(meow.execute)
    if month_exists.data:
        reply1 = await interaction.followup.send(f"**Sets have already been collected for {month.value} {year.value}!**")
        await channel.delete_messages([reply1])
        return

    spotlights_set = bot.get_channel(spotlights_set_id)
    await spotlights_set.send(f"# =================== {month.value} {year.value} Spotlight Sets ===================")
    reply2 = await interaction.followup.send(f"**Set collection started for {month.value} {year.value}!**")
    month_end = lappland.table("spotlight_month").update({
        "active": False
    }).eq("active", True)
    await asyncio.to_thread(month_end.execute)

    opening_month = lappland.table("spotlight_month").insert({
    "spotlight_month": f"{month.value} {year.value}",
    "active": True
    })
    await asyncio.to_thread(opening_month.execute)

    await channel.delete_messages([reply2])

texas = create_client(url, key) # need this to be global, since we only have 3 seconds to get the database from db (discord.py limitation)

async def month_autocomplete(interaction: discord.Interaction, current: str):
    meow = texas.table("spotlight_month").select("spotlight_month").eq("active", True)
    all_month = await asyncio.to_thread(meow.execute)
    months = [row["spotlight_month"] for row in all_month.data]
    return [
        app_commands.Choice(name=month, value=month)
        for month in months
        if current.lower() in month.lower()
    ]

async def formats_autocomplete(interaction: discord.Interaction, current: str):
    month = interaction.namespace.month
    if not month:
        return []
    meow =  texas.table("spotlight_set").select("format").eq("spotlight_month", month)
    all_format = await asyncio.to_thread(meow.execute)
    formats = list(dict.fromkeys(row["format"] for row in all_format.data))
    return [
        app_commands.Choice(name=format, value=format)
        for format in formats
        if current.lower() in format.lower()
    ]

@bot.tree.command(name="generate_smogon_post", description="make the smogon spotlight post", guild=discord.Object(id=socmed_server))
@app_commands.describe(month="the month of the sets", formats="comma-separated list of formats, e.g. 'BSS, NatDex Ubers'")
@app_commands.autocomplete(month=month_autocomplete, formats=formats_autocomplete)
async def generate_smogon_post(interaction: discord.Interaction, month: str, formats: str,):
    await interaction.response.defer()
    if not staff_role(interaction):
        await interaction.followup.send("**You don't have permission.**", ephemeral=True)
        return

    format_list = [format.strip() for format in formats.split(",")]
    all_output = []
    lappland = create_client(url, key)

    for format in format_list:
        meow = lappland.table("spotlight_set").select("set, suggested_by").eq("format", format).eq("spotlight_month", month)  
        all_format = await asyncio.to_thread(meow.execute)

        if not all_format.data:
            continue

        all_suggesters = [row["suggested_by"] for row in all_format.data]
        unique_suggesters = list(dict.fromkeys(all_suggesters))
        suggester_str = " and ".join(f"@{s}" for s in unique_suggesters)

        smogon = [f"[B]{format}[/B], courtesy of {suggester_str}"]

        for row in all_format.data:
            pokemon_set = row["set"].strip()

            name_match = re.search(pokemon, pokemon_set, re.DOTALL)
            if not name_match:
                continue

            name = name_match.group(1).strip()

            # for spoiler tag, extracts everything after ":" 
            replay_match = re.search(r"Replay:\s*(.+)", pokemon_set, re.DOTALL)
            qc_match = re.search(r"QC Notes:\s*(.+)", pokemon_set, re.DOTALL)

            if qc_match:
                qc_notes = qc_match.group(1).strip()
                pokemon_set = re.sub(r"\n*QC Notes:.+", "", pokemon_set, flags=re.DOTALL).rstrip()
                spoiler = f'[SPOILER="QC Notes"]{qc_notes}[/SPOILER]'
            elif replay_match:
                replay_url = replay_match.group(1).strip()
                pokemon_set = re.sub(r"\n*Replay:.+", "", pokemon_set, flags=re.DOTALL).rstrip()
                spoiler = f'[SPOILER="Replay"]{replay_url}[/SPOILER]'
            else:
                pokemon_set = pokemon_set.rstrip()
                spoiler = ""

            smogon = smogon + f"\n:{name}:\n{pokemon_set}\n{spoiler}"
                
        all_output.append(smogon)

    if not all_output:
        await interaction.followup.send("**No sets found for these formats!**")
        return
        
    output = "\n\n".join(all_output)
    bbcode = discord.File(io.BytesIO(output.encode()), filename="spotlight_post.txt")
    await interaction.followup.send(file=bbcode)

bot.run(token)