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
from aiohttp import web
import traceback

# Self note: discord.py works with aync functions but create_client is sync. acreate_client gives network, so didn't wanna risk it. So call using create_client, then force it to async by wrapping it with asyncio.to_thread.

# source: https://youtu.be/sOwG0bw0RNU?si=0Ty_koXKlg21pSSk
load_dotenv()
token = os.getenv("token")
url = os.getenv("url")
key = os.getenv("key")
socmed_server = int(os.getenv("socmed_server"))
spotlights_id = int(os.getenv("spotlights_id"))
spotlights_set_id = int(os.getenv("spotlights_set_id"))
spotlight_staff = int(os.getenv("spotlight_staff"))
reaction = os.getenv("reaction")
reaction_id = int(os.getenv("reaction_id"))
PORT = int(os.getenv("PORT", 8080))

# regx pattern for different parts of spotlight message
spotlight_message = r"^.+ by .+\n?```[\s\S]+```$"
spotlight_sets = r"```([\s\S]+?)```"
individual_set = r"\n\s*\n"
set_suggester = r"(^.+) by"
set_format = r"by (.+)\n?```"
pokemon = r"^(.+?)\s*@"
qc_pattern = r'(?i)\bqc\b[^:]*:(.*)'
replay_pattern = r'(?i)\breplay\b[^:]*:(.*)'

async def handle_root(request):
    return web.Response(text="OK")

async def handle_keep_alive(request):
    return web.Response(text="OK")

def setup_routes(app):
    pass

@web.middleware
async def error_middleware(request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"error": str(e)}, status=500)

async def start_web_server():
    app = web.Application(middlewares=[error_middleware])
    app.router.add_get('/', handle_root)
    app.router.add_get('/keep-alive', handle_keep_alive)
    setup_routes(app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Web server started on port {PORT}")

async def I_am_alive(status: str):
    try:
        lappland = create_client(url, key)
        meow = lappland.table("bot_status").insert({"status": status})
        await asyncio.to_thread(meow.execute)
    except Exception as e:
        print(f"Failed to log status: {e}")

async def log(name, input=None, error=None):
    lappland = create_client(url, key)
    try:
        meow = lappland.table("bot_log").insert({
            "command/function/event": name,
            "inputs/content": input or "",
            "error": error or "",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        await asyncio.to_thread(meow.execute)
    except Exception as e:
        pass

# bot message id for raw_reaction, raw_edit, raw_delete
async def bot_message_id(message_id):
    await log("bot_message_id", message_id)
    try:
        lappland = create_client(url, key)
        meow = lappland.table("spotlight_set_message_id").select("bot_message_id").eq("user_message_id", message_id)
        id = await asyncio.to_thread(meow.execute)
        if not id.data:
            return None
        return id.data[0]["bot_message_id"]
    except Exception as e:
        await log("fucked_up", error=str(e))
        print("fucked up:",e)

async def get_month():
    await log("get_month")
    try:
        lappland = create_client(url, key)
        meow = lappland.table("spotlight_month").select("spotlight_month").eq("active", True)
        month = await asyncio.to_thread(meow.execute)
        if not month.data:
            return None
        return month.data[0]["spotlight_month"]
    except Exception as e:
        await log("fucked_up", error=str(e))
        print("fucked up:",e)

def spotlight_reaction(message, reaction, reaction_id):
    return any(
        r.emoji.name == reaction and r.emoji.id == reaction_id
        for r in message.reactions
    )

def staff_role(member):
    return any(role.id == spotlight_staff for role in member.roles)

async def store_set(message, month):
    try:
        lappland = create_client(url, key)
        blocks = re.findall(spotlight_sets, message.content)

        if len(blocks) == 1:
            sets = re.split(individual_set, blocks[0].strip())
        else:
            sets = [i.strip() for i in blocks]

        qcs = []
        replays = []
        sets2 = []
        for i in sets:
            if re.search(qc_pattern, i):
                qc = re.findall(qc_pattern, i)
                qcs.extend(qc)
                remove = re.sub(qc_pattern, '', i)
                sets2.append(remove)
            elif re.search(replay_pattern, i):
                replay = re.findall(replay_pattern, i)
                replays.extend(replay)
                remove = re.sub(replay_pattern, '', i)
                sets2.append(remove)
            else:
                sets2.append(i)
                replays.append(None)
                qcs.append(None)

        sets2 = ["\n".join(j.strip() for j in set.strip().splitlines()) for set in sets2]

        format = re.findall(set_format, message.content)[0]

        suggester = re.search(set_suggester, message.content)
        if suggester:
            suggesters = [i.strip() for i in suggester.group(1).split(" and ")]
        else:
            suggesters = ["NA"]

        pokemons = []
        for i in sets2:
            mon = re.findall(pokemon, i)
            pokemons.extend(mon)

        if len(suggesters) == len(sets2) == len(pokemons) == len(qcs) == len(replays):
            pairs = list(zip(pokemons, sets2, suggesters, qcs, replays))
        elif len(suggesters) == 1:
            pairs = [(mon, set, suggesters[0], qc, replay) for mon, set, qc, replay in zip(pokemons, sets2, qcs, replays)]
        else:
            pairs = [(mon, set, "NA", qc, replay) for mon, set, qc, replay in zip(pokemons, sets2, qcs, replays)]

        for mon, set, suggester, qc, replay in pairs:
            insert_set = lappland.table("spotlight_set").insert({
                "user_message_id": message.id,
                "format": format,
                "pokemon": mon,
                "set": set,
                "qc_notes": qc,
                "replay": replay,
                "suggested_by": suggester,
                "spotlight_month": month
            })
            await asyncio.to_thread(insert_set.execute)
    except Exception as e:
        await log("fucked_up", error=str(e))
        print("fucked up:",e)

class Client(commands.Bot):

    async def on_ready(self):
        await I_am_alive("online")  
        await log("on_ready")
        print(f'logged in as {self.user}!')

        try:
            synced = await self.tree.sync(guild=discord.Object(id=socmed_server))
            print(f'Synced {len(synced)} commands to server {socmed_server}')
        except Exception as e:
            await log("fucked_up", error=str(e))    
            print("fucked up:",e)   

        server = self.get_guild(socmed_server)
        spotlights_set = self.get_channel(spotlights_set_id)
        spotlights = self.get_channel(spotlights_id)

        if not server or not spotlights_set:
            return

        self.spotlights_set = self.get_channel(spotlights_set_id)

        start_1 = await spotlights.send("**Spotlight Sets Is Online!**")
        start_2 = await spotlights.send("**Fetching Messages...**")

        async def yes_callback(interaction):
            await interaction.response.defer() 

            guild = interaction.guild
            member = guild.get_member(interaction.user.id)

            if not staff_role(member):
                reply = await interaction.followup.send("*You don't have permission.*")
                await asyncio.sleep(1)
                await reply.delete()
                return
            lappland = create_client(url, key)
            meow = lappland.table("bot_status")\
                        .select("status, created_at")\
                        .eq("status", "offline")\
                        .order("created_at", desc=True)\
                        .limit(1)
            meowtwo = await asyncio.to_thread(meow.execute)
            if meowtwo.data:
                meowthree = meowtwo.data[0]["created_at"]
                last_offline = datetime.fromisoformat(meowthree).replace(tzinfo=timezone.utc)
            else:
                last_offline = None

            sent_date = datetime(2026, 4, 1, tzinfo=timezone.utc) # messages before April 1st go to old_spotlight_set_message_id, newer to spotlight_set_message_id
            button.stop()
            reply_1 = await interaction.followup.send("**Implementing changes...**")
            messages = [message async for message in spotlights.history(limit=None, after=last_offline)]
            messages.reverse()
            month = await get_month()
            for message in messages:
                try:
                    if not re.search(spotlight_message, message.content):
                        continue

                    if not last_offline or message.created_at < sent_date:
                        select_table = "old_spotlight_set_message_id"
                    elif spotlight_reaction(message, reaction, reaction_id):
                        select_table = "spotlight_set_message_id"
                    else:
                        continue

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
                            await store_set(message, month)
                        else:
                            stored_message = lappland.table(select_table).insert({
                                "user_message_id": message.id,
                                "spotlight_context": message.content
                            })
                        await asyncio.to_thread(stored_message.execute)
                        print(f"Inserted message {message.id} into {select_table}")
                        await asyncio.sleep(5)

                    else:
                        try:
                            bot_id = meow.data[0].get("bot_message_id")
                            if bot_id is None:
                                continue
                            existing_in_db = meow.data[0]["spotlight_context"]
                            if existing_in_db != message.content:
                                try:
                                    bot_edit = await spotlights_set.fetch_message(bot_id)
                                    await bot_edit.edit(content=message.content)
                                    edited_message = lappland.table(select_table).update({
                                        "last_edit": datetime.now(timezone.utc).isoformat(),
                                        "spotlight_context": message.content,
                                    }).eq("user_message_id", message.id)
                                    print(f"edited message {message.id} from select_table")
                                    await asyncio.to_thread(edited_message.execute)
                                    await store_set(message, month)
                                except discord.NotFound as e:
                                        await log("fucked_up", error=str(e))
                                        print("fucked up:",e)
                                        return
                                except discord.Forbidden as e:
                                    await log("fucked_up", error=str(e)) 
                                    print("fucked up:",e)
                            else:
                                await asyncio.sleep(5)
                        except discord.NotFound as e:
                            await log("fucked_up", error=str(e)) 
                            print("fucked up:",e)
                            await asyncio.sleep(5)
                except Exception as e:
                    await log("fucked_up", error=str(e))
                    print("fucked up:",e)
                    continue

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
                            print(f"deleted message {message_id['user_message_id']} from spotlight_set_message_id")
                            await asyncio.sleep(5)
                        except discord.NotFound as e:
                            await log("fucked_up", error=str(e)) 
                            print("fucked up:",e)
                            continue

            reply_2 = await spotlights.send("**Changes Implemented!**")
            await reply_1.delete()
            await spotlights.delete_messages([start_1, start_2])
            await start_3.delete()


        async def no_callback(interaction):
            await interaction.response.defer()

            guild = interaction.guild
            member = guild.get_member(interaction.user.id)

            if not staff_role(member):
                reply = await interaction.followup.send("*You don't have permission.*")
                await asyncio.sleep(1)
                await reply.delete()
                return
            
            button.stop()
            reply_3 = await interaction.followup.send("**Changes will not be implemented.**")
            await asyncio.sleep(2)
            await reply_3.delete()
            await spotlights.delete_messages([start_1, start_2])
            await start_3.delete()

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
        except discord.NotFound as e:
            await log("fucked_up", error=str(e)) 
            print("fucked up:",e)
            return

        if not re.search(spotlight_message, message.content):
            return
        
        await log("on_raw_reaction_add", payload.message_id)
        print(f"on_raw_reaction_add triggered for {payload.message_id}")

        lappland = create_client(url, key)
        month = await get_month()

        meow = lappland.table("spotlight_set_message_id").select("*").eq("user_message_id", message.id)
        existing_id = await asyncio.to_thread(meow.execute)
        if existing_id.data:
            return

        spotlights_set = self.get_channel(spotlights_set_id)
        try:
            store = await spotlights_set.send(message.content)
            inserted_message = lappland.table("spotlight_set_message_id").insert({
                "user_message_id": message.id,
                "bot_message_id": store.id,
                "spotlight_context": message.content,
                "spotlight_month": month
            })
            await asyncio.to_thread(inserted_message.execute)
            await store_set(message, month)
        except Exception as e:
            await log("fucked_up", error=str(e))
            print("fucked up:",e)

    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        if payload.guild_id is None or payload.guild_id != socmed_server or payload.channel_id != spotlights_id:
            return
        
        content = payload.data.get("content")
        if content is not None and not re.search(spotlight_message, content):
            return

        channel = self.get_channel(payload.channel_id)
        try:
            after = await channel.fetch_message(payload.message_id)
        except discord.NotFound as e:
            await log("fucked_up", error=str(e)) 
            print("fucked up:",e)
            return

        if after.author == self.user:
            return
        
        if not re.search(spotlight_message, after.content): 
            return
        
        spotlights_set = self.get_channel(spotlights_set_id)
        bot_id = await bot_message_id(payload.message_id)
        
        if bot_id is None:  
            return
        
        await log("on_raw_message_edit", payload.message_id)
        print(f"on_raw_message_edit triggered for {payload.message_id}")

        try:
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

            blocks = re.findall(spotlight_sets, after.content)

            if len(blocks) == 1:
                sets = re.split(individual_set, blocks[0].strip())
            else:
                sets = [i.strip() for i in blocks]

            qcs = []
            replays = []
            sets2 = []
            for i in sets:
                if re.search(qc_pattern, i):
                    qc = re.findall(qc_pattern, i)
                    qcs.extend(qc)
                    remove = re.sub(qc_pattern, '', i)
                    sets2.append(remove)
                elif re.search(replay_pattern, i):
                    replay = re.findall(replay_pattern, i)
                    replays.extend(replay)
                    remove = re.sub(replay_pattern, '', i)
                    sets2.append(remove)
                else:
                    sets2.append(i)
                    replays.append(None)
                    qcs.append(None)

            sets2 = ["\n".join(j.strip() for j in set.strip().splitlines()) for set in sets2]

            format = re.findall(set_format, after.content)[0]

            suggester = re.search(set_suggester, after.content)
            if suggester:
                suggesters = [i.strip() for i in suggester.group(1).split(" and ")]
            else:
                suggesters = ["NA"]

            pokemons = []
            for i in sets2:
                mon = re.findall(pokemon, i)
                pokemons.extend(mon)

            if len(suggesters) == len(sets2) == len(pokemons) == len(qcs) == len(replays):
                pairs = list(zip(pokemons, sets2, suggesters, qcs, replays))
            elif len(suggesters) == 1:
                pairs = [(mon, set, suggesters[0], qc, replay) for mon, set, qc, replay in zip(pokemons, sets2, qcs, replays)]
            else:
                pairs = [(mon, set, "NA", qc, replay) for mon, set, qc, replay in zip(pokemons, sets2, qcs, replays)]

            for mon, set, suggester, qc, replay in pairs:
                insert_set = lappland.table("spotlight_set").insert({
                    "user_message_id": payload.message_id,
                    "format": format,
                    "pokemon": mon,
                    "set": set,
                    "qc_notes": qc,
                    "replay": replay,
                    "suggested_by": suggester,
                    "spotlight_month": month
                })
                await asyncio.to_thread(insert_set.execute)
        except Exception as e:
            await log("fucked_up", error=str(e))
            print("fucked up:",e)
            
    async def on_raw_message_delete(self, payload: discord.RawMessageUpdateEvent):

        if payload.guild_id is None or payload.guild_id != socmed_server or payload.channel_id != spotlights_id:
            return
        
        if payload.cached_message and payload.cached_message.author == self.user:
            return  
        
        spotlights_set = self.get_channel(spotlights_set_id)
        bot_id = await bot_message_id(payload.message_id)
        if bot_id is None:
            return

        await log("on_raw_message_delete", payload.message_id)
        print(f"on_raw_message_delete triggered for {payload.message_id}")

        try:
            bot_delete = await spotlights_set.fetch_message(bot_id)
        except discord.NotFound as e:
            await log("fucked_up", error=str(e)) 
            print("fucked up:",e)
            return
                    
        channel = self.get_channel(spotlights_id)

        Yes = Button(label="Yes", style=discord.ButtonStyle.green)
        No = Button(label="No", style=discord.ButtonStyle.red)

        async def yes_callback(interaction):
            await interaction.response.defer()
            button.stop()
            guild = interaction.guild
            member = guild.get_member(interaction.user.id)

            if not staff_role(member):
                reply = await interaction.followup.send("*You don't have permission.*")
                await asyncio.sleep(1)
                await reply.delete()
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
                reply1 = await interaction.followup.send("**Message Deleted!**")
                await asyncio.sleep(2)
                await channel.delete_messages([prompt, reply1])
            except Exception as e:
                await log("fucked_up", error=str(e)) 
                print("fucked up:",e)

        async def no_callback(interaction):
            await interaction.response.defer()
            button.stop()
            guild = interaction.guild
            member = guild.get_member(interaction.user.id)

            if not staff_role(member):
                reply = await interaction.followup.send("*You don't have permission.*")
                await asyncio.sleep(1)
                await reply.delete()
                return
            
            reply2 = await interaction.followup.send("**Message will not be deleted.**")
            await asyncio.sleep(2)
            await channel.delete_messages([prompt, reply2])

        Yes.callback = yes_callback
        No.callback = no_callback

        button = View()
        button.add_item(Yes)
        button.add_item(No)
        prompt = await channel.send(f"**Do you wish to delete the message in https://discord.com/channels/{socmed_server}/{spotlights_set_id}/{bot_delete.id}?**", view=button)

    async def on_disconnect(self):
        await I_am_alive("offline")
        print(f'Bot has disconnected at [{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}]')
            
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
    await log("start_set_collection", f"{month.value} {year.value}")
    print(f"start_set_collection triggered")

    guild = interaction.guild
    member = guild.get_member(interaction.user.id)
    
    if not staff_role(member):
        reply = await interaction.followup.send("*You don't have permission.*")
        await asyncio.sleep(1)
        await reply.delete()
        return
    
    try:    
        lappland = create_client(url, key)
        channel = bot.get_channel(spotlights_id)
        meow = lappland.table("spotlight_month").select("*").eq("spotlight_month", f"{month.value} {year.value}")
        month_exists = await asyncio.to_thread(meow.execute)
        if month_exists.data:
            reply1 = await interaction.followup.send(f"**Sets have already been collected for {month.value} {year.value}!**")
            await asyncio.sleep(10)
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
        await asyncio.sleep(10)
        await channel.delete_messages([reply2])
    except Exception as e:
        await log("fucked_up", error=str(e)) 
        print("fucked up:",e)

@bot.tree.command(name="generate_spotlight_post", description="start collecting sets for the month", guild=discord.Object(id=socmed_server))
@app_commands.describe(month = "month of the post")
@app_commands.describe(format = "comma-separated formats e.g. BSS, NatDex Ubers")
async def generate_spotlight_post(interaction: discord.Interaction, month: str, format: str):
    await interaction.response.defer()
    await log("generate_spotlight_post", f"{month} {format}")
    print(f"generate_spotlight_post triggered")

    guild = interaction.guild
    member = guild.get_member(interaction.user.id)

    if not staff_role(member):
        reply = await interaction.followup.send("*You don't have permission.*")
        await asyncio.sleep(1)
        await reply.delete()
        return
    
# Step 1: Month and Formats are taken as input. 
# Step 2: For every format in the formats list, fetch "suggested_by". Then convert both into a dictionary, where Key is the "format" and "suggested_by" is stored as list. Set only store unqiue values, so first turning the "suggested_by" as a set, then converting it into a list is the best approach because I don't know how to manipulate sets.
# Step 3: For key and values in dictionary "result", build the header first, i.e., "[B]format[/B], courtesy of @suggeseter1 and @suggester2". 
# Step 4: Then fetch "pokemon names", "sets", "qc", "replays" for each format. 
# Step 5: For every format, print each set in sets.data.
# Step 6: Handle QC and Replay. Simplest solution was to store them separetely in the db at the time the set was originally stored in the db. Then if j["qc_notes"] is not NULL, store it to a variable qc, else store "empty string" in qc, which you will add to your print statement. Same with Replays
# Step 7: Append format into a list "bbcode". Print "\n".join(bbcode) outside the outer loop to get all the elements of the bbcode printed one line after another. Tp get a line gap between each format's block, append an "empty string" to bbcode outside the inner loop.
# So I can reuse this logic in other projects

    try:
        lappland = create_client(url, key)
        meow = lappland.table("spotlight_set")\
                    .select("*")\
                    .eq("spotlight_month", month)
        existing_month = await asyncio.to_thread(meow.execute)
        if not existing_month.data:
            reply1 = await interaction.followup.send(f"No entry exists for {month}!")
            await asyncio.sleep(1)
            await reply1.delete()
            return
        else:
            formats = []
            for i in format.split(","):
                    i = i.strip()
                    meow = lappland.table("spotlight_set")\
                            .select("*")\
                            .eq("format", i)\
                            .eq("spotlight_month", month)
                    existing_format = await asyncio.to_thread(meow.execute)
                    if not existing_format.data:
                            reply2 = await interaction.followup.send(f"Sets for {i} doesn't exist for {month}!")
                            await asyncio.sleep(1)
                            await reply2.delete()
                            return
                    else:
                            formats.append(i)
                    
            bbcode = []
            result = {}
            for i in formats:
                    meow = lappland.table("spotlight_set")\
                            .select("suggested_by")\
                            .eq("format", i)\
                            .eq("spotlight_month", month)
                    existing = await asyncio.to_thread(meow.execute)
                    result[i] = list(set(j["suggested_by"] for j in existing.data))

            for key, values in result.items():
                    header = (f"[B]{key}[/B], courtesy of {' and '.join(f'@{i}' for i in values)}")
                    bbcode.append(header)
                    meow = lappland.table("spotlight_set")\
                            .select("set","pokemon","qc_notes","replay")\
                            .eq("format", key)\
                            .eq("spotlight_month", month)
                    sets = await asyncio.to_thread(meow.execute)
                    for j in sets.data:
                            if j["qc_notes"]:
                                    qc = f'\n[Spoiler="QC Notes"]{j["qc_notes"]}[/Spoiler]'
                            else:
                                    qc = ""
                            if j["replay"]:
                                    replay = f'\n[Spoiler="Replay"]{j["replay"]}[/Spoiler]'
                            else:
                                    replay = ""
                            format_block = (f':{j["pokemon"]}:\n{j["set"]}{qc}{replay}')
                            bbcode.append(format_block)
                    bbcode.append("")

            bb = "\n".join(bbcode)
            bbcode_string = io.BytesIO(bb.encode("utf-8"))
            spotlight = discord.File(fp=bbcode_string, filename='spotlight.txt')
            reply3 = await interaction.followup.send(file=spotlight)
            await asyncio.sleep(900)
            await reply3.delete()
    except Exception as e:
        await log("fucked_up", error=str(e)) 
        print("fucked up:",e)
        reply4 = await interaction.followup.send("**Something went wrong!**")
        await asyncio.sleep(1)
        await reply4.delete()

@bot.tree.command(name="current_month_and_sets", description="check the current month and sets available", guild=discord.Object(id=socmed_server))
async def current_month_and_sets(interaction: discord.Interaction):
    await interaction.response.defer()
    await log("current_month_and_sets")
    print(f"current_month_and_sets triggered")

    guild = interaction.guild
    member = guild.get_member(interaction.user.id)

    if not staff_role(member):
        reply = await interaction.followup.send("*You don't have permission.*")
        await asyncio.sleep(1)
        await reply.delete()
        return
    
    try: 
        month = await get_month()
        formats = []
        lappland = create_client(url, key)
        meow = lappland.table("spotlight_set")\
                    .select("format")\
                    .eq("spotlight_month", month)
        format = await asyncio.to_thread(meow.execute)
        if not format.data:
            reply1 = await interaction.followup.send(f"No set exists for {month}!")
            await asyncio.sleep(1)
            await reply1.delete()
            return
        else:
            for i in format.data:
                if i["format"] not in formats:
                    formats.append(i["format"])
        reply2 = await interaction.followup.send(f"Current Month: {month}\nFomats Available: {formats}")
        await asyncio.sleep(900)
        await reply2.delete()
        return
    except Exception as e:
        await log("fucked_up", error=str(e)) 
        print("fucked up:",e)

async def run_bot():
    try:
        await bot.start(token)
    except Exception as e:
        await I_am_alive("offline")
        await log("bot_died", error=str(e))
        print(f'[{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}] Bot died: {e}')
        traceback.print_exc()

async def run_web_server():
    try:
        await start_web_server()
        await asyncio.Future()
    except Exception as e:
        print(f'[{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}] Web server died: {e}')
        traceback.print_exc()

async def main():
    await asyncio.gather(
        run_web_server(),
        run_bot()
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Stopped manually.')
    except Exception as e:
        print(f'[{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}] main() crashed: {e}')
        traceback.print_exc()
