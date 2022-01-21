import asyncio
import discord
from json import load, dumps
from io import StringIO
import subprocess as sp
import math
import numpy as np
import os
import random

token = "Njg3NjE4NTEwMjgwODUxNDk3.XmoYpA.EgWeicaOkeinPw9Txq-wW4S-qMU"
dataChannelId = 904777404155842601
data = {}
client = discord.Client()
syncChannel: discord.TextChannel
endMessage = True
maxMessageLength = 2000

# updates discord message according to local data file
async def export_data():
    dataFile = open("tssbdata.json", 'w')
    dataFile.write(dumps(data, indent=2))
    dataFile.close()
    await syncChannel.send(file=discord.File(fp="tssbdata.json"))

# updates local data file according to discord message
async def import_data():
    global data
    dataMessage = ''
    async for message in syncChannel.history(limit=1):
        dataMessage = message
    fileObject = dataMessage.attachments[0]
    await fileObject.save(fp="tssbdata.json")
    dataFile = open("tssbdata.json", 'r')
    dataContent = dataFile.read()
    dataFile.close()
    data = load(StringIO(dataContent))

def extract_id(idWord):
    start = 0
    end = len(idWord)-1
    while start < len(idWord):
        if idWord[start].isdigit():
            break
        start += 1
    while end >= 0:
        if idWord[end].isdigit():
            break
        end -= 1
    return int(idWord[start:end+1])

def remove_start_space(text):
    count = 0
    while count < len(text):
        letter = text[count]
        if letter != ' ' and letter != '\n':
            break
        count += 1
    return text[count:]

def split_next_word(text):
    text = remove_start_space(text)
    count = 0
    while count < len(text):
        letter = text[count]
        if letter == ' ' or letter == '\n':
            break
        count += 1
    if count == len(text):
        return text, ''
    return text[:count], remove_start_space(text[count:])

def align_lines(lines):
    for lineNo, line in enumerate(lines):
        if len(line) > maxMessageLength:
            words = line.split(' ')
            for wordNo, word in enumerate(words):
                if len(word) > maxMessageLength:
                    words[wordNo] = word[:maxMessageLength]
                    words.insert(wordNo + 1, word[maxMessageLength:])
            tempWords = words.copy()
            words = []
            while len(tempWords) > 1:
                while len(tempWords[0]) + len(tempWords[1]) < maxMessageLength:
                    tempWords[0] += ' ' + tempWords.pop(1)
                    if len(tempWords) == 1:
                        break
                words.append(tempWords.pop(0))
            if len(tempWords) == 1:
                words.append(tempWords.pop(0))
            words.reverse()
            for i in range(len(words)):
                lines.insert(lineNo + 1, words.pop(0))
            lines.pop(lineNo)
    tempLines = lines.copy()
    lines = []
    while len(tempLines) > 1:
        while len(tempLines[0]) + len(tempLines[1]) < maxMessageLength:
            tempLines[0] += '\n' + tempLines.pop(1)
            if len(tempLines) == 1:
                break
        lines.append(tempLines.pop(0))
    if len(tempLines) == 1:
        lines.append(tempLines.pop(0))
    return lines

def get_prefixes(message):
    if str(message.author.id) in data["userPrefixes"]:
        return data["userPrefixes"][str(message.author.id)] + [f"<@!{client.user.id}>"]
    else:
        return data["globalPrefixes"] + [f"<@!{client.user.id}>"]

def replace_math(text):
    textCopy = text
    positions = []
    while True:
        letterDif = textCopy.find('$')
        if letterDif == -1:
            break
        if letterDif == 0 or textCopy[letterDif - 1] != '\\':
            positions.append(len(text) - len(textCopy) + letterDif)
        textCopy = textCopy[letterDif + 1:]
    if len(positions) % 2 == 1:
        positions.pop()
    if len(positions) == 0:
        return
    textCopy = text
    positions.reverse()
    for i in range(len(positions) // 2):
        try:
            result = str(eval(textCopy[positions[2 * i + 1] + 1:positions[2 * i]]))
            if '\n' not in result and result[0] == '[' and result[2] == ']':
                result = result[4:]
        except SyntaxError as err:
            result = "Syntax Error: {0}".format(err)
        text = text[:positions[2 * i + 1]] + result + text[positions[2 * i] + 1:]
    return text

async def c_help(message, messageContent, initialCommand):
    messageChannel = message.channel
    helpEmbed = discord.Embed()
    if len(messageContent) == 0:
        helpEmbed.set_footer(text="To get more info on a command, do b!help {commandName}")
        helpEmbed.set_author(name="Command List",
                             icon_url="https://cdn.discordapp.com/emojis/912192772730130462.png")
        helpEmbed.add_field(name="Use",
                            value="`python` `commandline` `impersonate` `colour` `purge` `echo`")
        helpEmbed.add_field(name="Settings",
                            value="`help` `ping` `admin` `prefix` `toggleendmessage` `exportdata`")
        await messageChannel.send(embed=helpEmbed)

    descriptions = [["p {pythonCode}",
                     "Runs python code and displays output.\n Runs code at once so delays also delay output.",
                     ["python", 'p']]]
    for description in descriptions:
        for alias in description[2]:
            if len(messageContent) >= len(alias):
                if alias.lower() == messageContent[:len(alias)].lower():
                    await messageChannel.send("test")
                    return

async def c_get_help(message, command):
    await message.channel.send("Run **{0}help {1}** to see usages for "
                               "**{0}{1}**.".format(get_prefixes(message)[0], command))

async def c_prefix(message, messageContent, initialCommand):
    messageChannel = message.channel
    if len(messageContent) == 0:
        await c_get_help(message, initialCommand)
        return
    command, messageContent = split_next_word(messageContent)
    userId = str(message.author.id)
    messageContent = split_next_word(messageContent)[0]
    if command in ["addglobalprefix", 'agp']:
        if userId not in data["admins"]:
            await messageChannel.send("Insufficient authority.")
            return
        if len(messageContent) == 0:
            await messageChannel.send("Specify a prefix to add.")
            return
        if messageContent in data["globalPrefixes"]:
            await messageChannel.send("Prefix already exists.")
            return
        data["globalPrefixes"].append(messageContent)
        await export_data()
        await messageChannel.send(f"Added global prefix \"{messageContent}\".")
        return
    if command in ["removeglobalprefix", 'rgp']:
        if userId not in data["admins"]:
            await messageChannel.send("Insufficient authority.")
            return
        if len(messageContent) == 0:
            await messageChannel.send("Specify a prefix to remove.")
            return
        if messageContent not in data["globalPrefixes"]:
            await messageChannel.send("Prefix doesn't exist.")
            return
        data["globalPrefixes"].remove(messageContent)
        await export_data()
        await messageChannel.send(f"Removed global prefix \"{messageContent}\".")
        return
    if command in ["adduserprefix", 'aup']:
        if len(messageContent) == 0:
            await messageChannel.send("Specify a prefix to add.")
            return
        if userId in data["userPrefixes"]:
            if messageContent in data["userPrefixes"][userId]:
                await messageChannel.send("Prefix already exists.")
                return
        else:
            data["userPrefixes"][userId] = []
        data["userPrefixes"][userId].append(messageContent)
        await export_data()
        await messageChannel.send(f"Added user prefix \"{messageContent}\".")
        return

    if command in ["removeuserprefix", 'rup']:
        if len(messageContent) == 0:
            await messageChannel.send("Specify a prefix to remove.")
            return
        if userId not in data["userPrefixes"]:
            await messageChannel.send("Prefix doesn't exist.")
            return
        if messageContent not in data["userPrefixes"][userId]:
            await messageChannel.send("Prefix doesn't exist.")
            return
        data["userPrefixes"][userId].remove(messageContent)
        if len(data["userPrefixes"][userId]) == 0:
            data["userPrefixes"].pop(userId)
        await export_data()
        await messageChannel.send(f"Removed user prefix \"{messageContent}\".")
        return
    await c_get_help(message, initialCommand)

async def c_purge(messageChannel, messageContent):
    try:
        amount = int(split_next_word(messageContent)[0])
    except ValueError:
        await messageChannel.send("Not an integre.")
        return
    messages = await messageChannel.history(limit=amount + 1).flatten()
    messages.pop(0)
    batches = amount // 100
    leftover = amount % 100
    if messageChannel.type == discord.ChannelType.private:
        for message in messages:
            if message.author.id == client.user.id:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
        await messageChannel.send(f"Removed my messsages up to {amount} messages ago.")
        return
    try:
        for batchNo in range(batches):
            await messageChannel.delete_messages(messages[batchNo * 100:(batchNo + 1) * 100])
        await messageChannel.delete_messages(messages[batches * 100:batches * 100 + leftover])
        await messageChannel.send(f"Removed {amount} messages.")
    except discord.errors.HTTPException:
        await messageChannel.send("Can't bulk delete messages over 2 weeks old.")

async def c_echo(message, messageContent):
    messageChannel = message.channel
    if len(remove_start_space(messageContent)) == 0:
        await messageChannel.send("Can't echo empty message.")
        return
    await messageChannel.send(messageContent)

async def c_ping(messageChannel):
    await messageChannel.send(f'{round(client.latency * 1000)}ms.')

async def c_admin(message, messageContent, initialCommand):
    messageChannel = message.channel
    if str(message.author.id) not in data["admins"]:
        await messageChannel.send("Insufficient authority.")
        return
    command, messageContent = split_next_word(messageContent)
    user = message.guild.get_member_named(split_next_word(messageContent)[0])
    if not user:
        try:
            user = await message.guild.fetch_member(extract_id(split_next_word(messageContent)[0]))
        except ValueError:
            pass
    if not command:
        await c_get_help(message, initialCommand)
        return
    if command in ["add", 'a']:
        if user:
            if str(user.id) in data["admins"]:
                await messageChannel.send(f"{user.name} is already an admin.")
                return
            data["admins"].append(str(user.id))
            await export_data()
            await messageChannel.send(f"{user.name} is now an admin.")
    elif command in ["remove", 'r']:
        if user:
            if str(user.id) not in data["admins"]:
                await messageChannel.send(f"{user.name} is not an admin.")
                return
            data["admins"].remove(str(user.id))
            await export_data()
            await messageChannel.send(f"{user.name} is no longer an admin.")
    else:
        await c_get_help(message, initialCommand)
        return
    if not user:
        await messageChannel.send("User not found.")

async def c_toggle_end_message(message, messageContent):
    messageContent = split_next_word(messageContent)[0]
    messageChannel = message.channel
    if messageContent == "global" or messageContent == 'g':
        if str(message.author.id) not in data["admins"]:
            await messageChannel.send("Insufficient authority.")
            return
        if "global" in data["toggleEndMessage"]:
            data["toggleEndMessage"].remove("global")
        else:
            data["toggleEndMessage"].append("global")
        await messageChannel.send("Toggled global end messages.")
    else:
        if str(message.author.id) in data["toggleEndMessage"]:
            data["toggleEndMessage"].remove(str(message.author.id))
        else:
            data["toggleEndMessage"].append(str(message.author.id))
        await messageChannel.send("Toggled user end messages.")
    await export_data()

async def c_command_line(message, messageContent, initialCommand):
    messageChannel = message.channel
    command, messageContent = split_next_word(messageContent)
    if str(message.author.id) not in data["admins"]:
        await messageChannel.send("Insufficient authority.")
        return
    if command in ["full", 'f']:
        output = sp.getoutput(messageContent).split('\n')
        for message in align_lines(output):
            try:
                await messageChannel.send(message)
            except discord.HTTPException:
                pass
    elif command in ["run", 'r']:
        process = sp.Popen(messageContent, stdout=sp.PIPE, stderr=sp.PIPE, encoding='utf8', shell=True)
        while True:
            output = process.stdout.readline()
            if output == "":
                break
            await messageChannel.send(align_lines(output.split('\n')))
    elif command in ["none", 'n']:
        sp.call(messageContent.split(' '))
    else:
        await c_get_help(message, initialCommand)

async def c_impersonate(message, messageContent, initialCommand):
    messageChannel = message.channel
    target, messageContent = split_next_word(messageContent)
    # if str(message.author.id) not in data["admins"]:
    #     await messageChannel.send("Insufficient authority.")
    #     return
    if len(messageContent) == 0:
        await c_get_help(message, initialCommand)
        return
    user = message.guild.get_member_named(target)
    if not user:
        try:
            user = await message.guild.fetch_member(extract_id(target))
        except ValueError:
            await c_get_help(message, initialCommand)
            return
    tempWebHook = await messageChannel.create_webhook(name=user.display_name)
    await tempWebHook.send(messageContent, avatar_url=user.avatar_url)
    await tempWebHook.delete()

async def c_color(message, messageContent, initialCommand):
    colourStr = split_next_word(messageContent)[0]
    if len(colourStr) != 6:
        await c_get_help(message, initialCommand)
    try:
        colourInt = int(colourStr, 16)
    except ValueError:
        await c_get_help(message, initialCommand)
        return
    for role in message.author.roles:
        if role.name[0] == '#':
            print(role.name)
    colourRole = await message.guild.create_role(name='#' + colourStr, color=colourInt)
    positions = {}
    for role in message.guild.roles:
        positions[role] = role.position
    highestPosition = 1
    for role, position in enumerate(positions):
        print(role)
        if position > 0:
            if position > highestPosition:
                highestPosition = position
            positions[role] = position - 1
    positions[colourRole] = highestPosition
    print(positions)
    # await message.guild.edit_role_positions(positions=positions)

async def c_python(message, messageContent):
    messageChannel = message.channel
    pythonFile = open("aaa.py", 'w')
    removedLines = []
    messageContent = messageContent.split('\n')
    for lineNo, line in enumerate(messageContent):
        if line.startswith("```"):
            removedLines.append(lineNo)
    for lineNo in reversed(removedLines):
        messageContent.pop(lineNo)
    messageContent = '\n'.join(messageContent)
    pythonFile.write(messageContent)
    pythonFile.close()
    await messageChannel.send(sp.getoutput(f"python3 aaa.py"))
    os.remove("aaa.py")

async def c_manual_data(message, messageContent):
    messageChannel = message.channel
    if str(message.author.id) not in data["admins"]:
        await messageChannel.send("Insufficient authority.")
        return
    if len(messageContent) == 0:
        await export_data()
    else:
        dataFile = open("tssbdata.json", 'w')
        dataFile.write(dumps(data, indent=2))
        dataFile.close()
        await syncChannel.send(file=discord.File(fp="tssbdata.json"))

async def c_pin(message: discord.Message, messageContent: str):
    if message.reference:
        pinMessageChannel: discord.TextChannel = await client.fetch_channel(message.reference.channel_id)
        pinMessage = await pinMessageChannel.fetch_message(message.reference.message_id)
        await pinMessage.pin(reason=str(message.id))
        return
    if len(messageContent) == 0:
        return
    slashIndex = messageContent.rfind('/')
    try:
        if slashIndex == -1:
            pinMessageId = int(messageContent)
        else:
            pinMessageId = int(messageContent[slashIndex+1:])
    except ValueError:
        return
    pinMessage = await message.channel.fetch_message(pinMessageId)
    await pinMessage.pin(reason=str(message.id))

# based on poketwo
async def poketwo_hint(message):
    messageContent = message.content
    messageChannel = message.channel
    region = ''
    nameOfPokemon = messageContent[15:len(messageContent) - 1].replace("\\_", '^')
    nameCopy = nameOfPokemon
    while True:
        pokemonList = load(open("pokemonList.json", 'r'))["pokemonList"]
        for count in range(len(pokemonList) - 1, -1, -1):
            if len(pokemonList[count]) != len(nameCopy):
                pokemonList.pop(count)
                continue
            for char in range(len(nameCopy)):
                if nameCopy[char] == '^':
                    continue
                if nameCopy[char] != pokemonList[count][char]:
                    pokemonList.pop(count)
                    break
        if len(pokemonList) > 0 or nameCopy.find(' ') == -1:
            break
        region, nameCopy = split_next_word(nameCopy)

    if len(pokemonList) == 0:
        possiblePokemons = "Pokémon not in the list, weirdly enough."
    else:
        if region != '':
            if len(region) == 4:
                region = "Pa'u"
            elif len(region) == 6:
                region = "Alolan "
            elif len(region) == 8:
                region = "Galarian "
        possiblePokemons = region + pokemonList.pop(0)
        for pokemon in pokemonList:
            possiblePokemons = possiblePokemons + "\n" + region + pokemon
    await messageChannel.send(possiblePokemons)

async def run_command(message, messageContent):
    messageChannel = message.channel
    command, messageContent = split_next_word(messageContent)
    command = str.lower(command)

    # commands
    if command in ["ping", 'pn']:
        await c_ping(messageChannel)
    elif command in ["help", 'h']:
        await c_help(message, messageContent, command)
    elif command in ["prefix", 'pf']:
        await c_prefix(message, messageContent, command)
    elif command in ["purge", 'pr']:
        await c_purge(messageChannel, messageContent)
    elif command in ["echo", "say", 's']:
        await c_echo(message, messageContent)
    elif command in ["admin", 'ad']:
        await c_admin(message, messageContent, command)
    elif command in ["toggleendmessage", "tem"]:
        await c_toggle_end_message(message, messageContent)
    elif command in ["manualdata", "mdata", 'md']:
        await c_manual_data(message, messageContent)
    elif command in ["commandline", 'cl']:
        await c_command_line(message, messageContent, command)
    elif command in ["pin", 'p']:
        await c_pin(message, messageContent)
    elif command in ["impersonate", 'imp']:
        await c_impersonate(message, messageContent, command)
    elif command in ["color", "colour", 'c']:
        await c_color(message, messageContent, command)
    elif command in ["python", 'p']:
        await c_python(message, messageContent)
    else:
        if messageChannel.type == discord.ChannelType.private and message.author.id == client.user.id:
            return
        await messageChannel.send("Not a command.")
    if ("global" in data["toggleEndMessage"]) + (str(message.author.id) in data["toggleEndMessage"]) == 1:
        return
    await messageChannel.send(data["endMessage"])

@client.event
async def on_ready():
    global syncChannel
    syncChannel = await client.fetch_channel(dataChannelId)
    await import_data()
    await client.change_presence(status=discord.Status.idle,
                                 activity=discord.Game(data["status"]))
    print(data["startMessage"])

@client.event
async def on_message(message: discord.Message):
    messageContent = message.content
    messageChannel = message.channel
    author = message.author
    if message.channel.type == discord.ChannelType.private:
        await run_command(message, messageContent)
        return
    else:
        for alias in get_prefixes(message):
            if alias == messageContent[:len(alias)]:
                await run_command(message, messageContent[len(alias):])
                return

        # based on poketwo
        if messageContent[:15] == "The pokémon is ":
            await poketwo_hint(message)
            return
    if author.bot:
        return
    mathifiedText = replace_math(message.content)
    if mathifiedText:
        tempWebHook = await messageChannel.create_webhook(name=author.display_name)
        await tempWebHook.send(mathifiedText, avatar_url=author.avatar_url)
        await message.delete()
        await tempWebHook.delete()

client.run(token)
