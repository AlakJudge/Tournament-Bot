import discord

from utils.debug import set_debug_mode, add_dummy_players, clean_dummy_players, is_debug_mode_enabled
from utils.helpers import validate_image_url, tournament_lock
from tournament import Tournament

def register_commands(bot, version):
    # Slash command to CREATE a new tournament
    @bot.slash_command(name="create", description="Create a new tournament")
    async def create(
        ctx: discord.ApplicationContext,
        registration_channel = discord.Option(
            discord.TextChannel,  # Only allow text channels
            description="The channel where player registration for the tournament will take place",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news]
            ),
        player_cap = discord.Option(
            int, # Only allows integers
            description="The maximum number of players that can register for the tournament (before reserves are added)"
            ),
        embed_image = discord.Option(
            str,
            description="The URL of the tournament embed image",
            required=False
            )
        ):
        
        from views.management import Create_Tournament
        
        # Only allow users with this permission to admin tournaments
        user: discord.Member = ctx.guild.get_member(ctx.user.id)
        organizer_role: discord.Role | None = discord.utils.get(ctx.guild.roles, name="BGTB Organizer")
        if organizer_role not in user.roles and not user.guild_permissions.administrator:
            await ctx.respond("Failed. You must have the 'BGTB Organizer' role to perform this action.", ephemeral=True)
            return   

        # Set permissions for bot to manage the registration channel
        overwrites = discord.PermissionOverwrite()
        overwrites.send_messages = True
        overwrites.read_messages = True
        overwrites.read_message_history = True
        overwrites.manage_messages = True
        overwrites.view_channel = True
        try:
            await registration_channel.set_permissions(ctx.guild.me, overwrite=overwrites)
        except discord.Forbidden as e:
            print(f"Failed to set permissions: {e}")
            await ctx.respond("Failed. The bot does not have permission to set channel permissions. Make sure the bot has the 'View Channel' and 'Manage Channels' permissions", ephemeral=True)
            return

        # Validate the image URL
        if embed_image:
            if not await validate_image_url(embed_image):
                await ctx.respond("Invalid image URL. Please provide a valid image URL starting with 'http://' or 'https://'", ephemeral=True)
                return

        # Display the Modal requesting input from the user
        modal = Create_Tournament(reg_channel=registration_channel, title="Create Tournament", player_cap=player_cap, image=embed_image)
        await ctx.send_modal(modal)

    # Slash command to display a LIST OF ALL ACTIVE TOURNAMENTS
    @bot.slash_command(name="tournaments_list", description="Show a list of all active tournaments and their ID numbers")
    async def tournament_list(ctx: discord.ApplicationContext):
        tournaments = Tournament.load_all_tournaments(ctx.guild.id)
        list = discord.Embed(title="List of Tournaments", color=discord.Color.blue())

        # Loop to add each tournament from the tournaments list
        for t in tournaments:
            list.add_field(name=f"({t.id}) - {t.name}", value=f"Game: {t.game}", inline=False)
        
        await ctx.respond(embed=list)


    # Slash command to ADMIN a tournament
    @bot.slash_command(name = "admin", description = "Administrate a Tournament by entering its ID number.")
    async def admin(
        ctx: discord.ApplicationContext, 
        id = discord.Option(description="Find this ID number by using the tournaments_list command")
        ):
        await ctx.defer()
        
        from views.admin_menu import T_Admin

        # Find the tournament
        tournaments = Tournament.load_all_tournaments(ctx.guild.id)
        tournament: Tournament = next((t for t in tournaments if t.id == int(id)), None) # Go through all tournaments and find the id entered.

        if not tournament:
            await ctx.followup.send("Tournament not found.", ephemeral=True)
            return
        
        # Only allow users with this permission to admin tournaments
        user: discord.Member = ctx.guild.get_member(ctx.user.id)
        admin_role: discord.Role = discord.utils.get(ctx.guild.roles, name=tournament.admin_role)
        if admin_role not in user.roles and not user.guild_permissions.administrator:
            await ctx.followup.send("Failed. Only Tournament Admins have permission to perform this action.", ephemeral=True)
            return
            
        view = T_Admin(tournament)
        embed = view.get_embed()
        await ctx.followup.send("", view=view, embed=embed)

        admin_msg = await ctx.interaction.original_response()
        tournament.admin_msg_id = admin_msg.id
        tournament.admin_msg_channel_id = admin_msg.channel.id
        tournament.save()

    # Slash command to set registration channel
    @bot.slash_command(name="set_reg_channel", description="Set the registration channel for your tournament")
    async def set_reg_channel(ctx: discord.ApplicationContext, tournament_id: int, registration_channel = discord.Option(
            discord.abc.GuildChannel, # Allow any channel type
            description="The channel where player registration for the tournament will take place",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news]
            )):
        # Get tournament
        tournaments = Tournament.load_all_tournaments(ctx.guild.id) # 
        tournament: Tournament = next((t for t in tournaments if t.id == int(tournament_id)), None)
        if not tournament:
            await ctx.respond("Tournament not found.", ephemeral=True)
            return

        # Only allow users with this permission to admin tournaments
        user: discord.Member = ctx.guild.get_member(ctx.user.id)
        admin_role: discord.Role = discord.utils.get(ctx.guild.roles, name=tournament.admin_role)
        if admin_role not in user.roles and not user.guild_permissions.administrator:
            await ctx.respond(f"Failed. You must have the '{tournament.admin_role}' role to perform this action.", ephemeral=True)
            return

        # Set permissions for bot to manage the registration channel
        overwrites = registration_channel.overwrites_for(ctx.guild.me)
        overwrites.send_messages = True
        overwrites.read_messages = True
        overwrites.read_message_history = True
        overwrites.manage_messages = True
        overwrites.view_channel = True
        await registration_channel.set_permissions(ctx.guild.me, overwrite=overwrites)

        # Set the registration channel and send confirmation
        tournament.set_reg_channel(registration_channel.id)
        tournament.save()
        await ctx.respond(f"Registration channel set to {registration_channel.mention}", ephemeral=True)

    # Slash command to reload initial thread message/view
    @bot.slash_command(name="reload_thread_buttons", description="Reload the initial thread message and buttons", )
    async def reload_thread_buttons(ctx: discord.ApplicationContext):    
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.respond("This command can only be used in a tournament thread.", ephemeral=True)
            return
        
        from views.running.match_views import Start_Match_View
        
        # Get the channel ID of the parent channel of the current thread, then get the tournament
        parent_channel_id = ctx.channel.parent_id 
        tournaments = Tournament.load_all_tournaments(ctx.guild.id)
        tournament: Tournament = next((t for t in tournaments if t.tournament_channel_id == parent_channel_id), None) 
        if not tournament:
            await ctx.respond("Tournament not found.", ephemeral=True)
            return

        # Only allow users with this permission to admin tournaments
        user: discord.Member = ctx.guild.get_member(ctx.user.id)
        admin_role: discord.Role = discord.utils.get(ctx.guild.roles, name=tournament.admin_role)
        if admin_role not in user.roles and not user.guild_permissions.administrator:
            await ctx.respond(f"Failed. You must have the '{tournament.admin_role}' role to perform this action.", ephemeral=True)
            return

        # Get the match id based on the current thread ID
        match_id = next((match["id"] for match in tournament.matches if match.get("thread_id") == ctx.channel.id), None)
        if not match_id:
            await ctx.respond("Match not found for this thread.", ephemeral=True)
            return
    
        # Reload the initial thread admin buttons
        view = Start_Match_View(match_id, tournament)
        await ctx.respond(content="## 🛠 Match Admin Buttons", view=view)

    @bot.slash_command(name="reload_tournament_menu", description="Reload the tournament admin menu")
    async def reload_tournament_menu(ctx: discord.ApplicationContext, tournament_id: int):
        
        from views.running.tournament_view import Tournament_Running_View
        
        # Get tournament
        tournaments = Tournament.load_all_tournaments(ctx.guild.id)
        tournament: Tournament = next((t for t in tournaments if t.id == int(tournament_id)), None)
        if not tournament:
            await ctx.respond("Tournament not found.", ephemeral=True)
            return
        
        # Only allow users with this permission to admin tournaments
        user: discord.Member = ctx.guild.get_member(ctx.user.id)
        admin_role: discord.Role = discord.utils.get(ctx.guild.roles, name=tournament.admin_role)
        if admin_role not in user.roles and not user.guild_permissions.administrator:
            await ctx.respond(f"Failed. You must have the '{tournament.admin_role}' role to perform this action.", ephemeral=True)
            return

        # Only allow command to be run in tournament chat
        if ctx.channel.id != tournament.tournament_channel_id:
            await ctx.respond("This command can only be used in the tournament channel.", ephemeral=True)
            return

        # Reload the admin menu
        view = Tournament_Running_View(tournament)
        await ctx.respond("## Tournament Admin Menu", view=view)

    # Register a player to a tournament manually
    @bot.slash_command(name="register_player", description="Register a player to a tournament manually")
    async def register_player(
            ctx: discord.ApplicationContext,
            tournament_id: int,
            player: discord.Member = discord.Option(discord.Member, description="The player to register to the tournament")
            ):
        
        from views.registration import register_player_to_tournament

        # Get tournament
        tournaments = Tournament.load_all_tournaments(ctx.guild.id)
        tournament: Tournament = next((t for t in tournaments if t.id == int(tournament_id)), None)
        if not tournament:
            await ctx.respond("Tournament not found.", ephemeral=True)
            return

        # Only allow users with this permission to admin tournaments
        user: discord.Member = ctx.guild.get_member(ctx.user.id)
        admin_role: discord.Role = discord.utils.get(ctx.guild.roles, name=tournament.admin_role)
        if admin_role not in user.roles and not user.guild_permissions.administrator:
            await ctx.respond(f"Failed. You must have the '{tournament.admin_role}' role to perform this action.", ephemeral=True)
            return
        
        async with tournament_lock:
            # Register the player
            await register_player_to_tournament(tournament, player, ctx.interaction)

    @bot.slash_command(name="help", description="Get help with the bot")
    async def help(ctx: discord.ApplicationContext):
        from views.help import HelpView
        
        help_embed = discord.Embed(title="Tournament Bot Help", color=discord.Color.blue())
        help_embed.add_field( 
            name="Description",
            value="This bot is designed to help you create and manage tournaments in your Discord server without relying on slash commands for almost anything. "
            "You can run and manage tournaments smoothly with just menus and buttons.\n\n"
            "*Use the buttons below to navigate the help menu and learn about each section of the bot.*\n**-----**\n", 
            inline=False
            )
        help_embed.add_field(
            name="🔹 Commands",
            value="Learn about the few slash commands available.", 
            inline=False
        )
        help_embed.add_field(
            name="🔹 Tournament Setup",
            value="Learn about how you can set up a tournament.", 
            inline=False
        )
        help_embed.add_field(
            name="🔹 Admin Menu",
            value="Learn all about the admin menu and how to use it.", 
            inline=False
        )
        help_embed.add_field(
            name="🔹 Running the Tournament",
            value="Learn how to run the tournament and manage players.", 
            inline=False
        )
        help_embed.add_field(
            name="🔸 Support Server",
            value="Join our support server for help and updates: [Support Server](https://discord.gg/4vSG9VYCyj)\n"
            "**---**",
            inline=False
        )
        help_embed.set_footer(text=f"Tournament Bot - {version}")

        # Create a view to hold the buttons
        view = HelpView(help_embed)

        # Show embed and buttons
        await ctx.respond(embed=help_embed, view=view, ephemeral=True)
        
    @bot.slash_command(name="debug_mode", description="Toggle debug mode for testing", guild_ids=[1286841607576092763]) 
    async def debug_mode(ctx: discord.ApplicationContext, enabled: bool):
        # Only allow users with this permission to admin tournaments
        user: discord.Member = ctx.guild.get_member(ctx.user.id)
        admin_role: discord.Role = discord.utils.get(ctx.guild.roles, name="BGTB Organizer")
        if admin_role not in user.roles and not user.guild_permissions.administrator:
            await ctx.respond("Failed. Only Tournament Admins have permission to perform this action.", ephemeral=True)
            return   
                
        set_debug_mode(enabled)
        status = "enabled" if enabled else "disabled"
        await ctx.respond(f"Debug mode {status}.", ephemeral=True)

    @bot.slash_command(name="add_dummies", description="Add dummy players to tournament (Debug mode only)", guild_ids=[1286841607576092763])
    async def add_dummies(ctx: discord.ApplicationContext, tournament_id: int, count: int = 50):        
        
        if not is_debug_mode_enabled():
            await ctx.respond("Debug mode not enabled.", ephemeral=True)
            return
        
        tournament = Tournament.load_tournament_by_id(ctx.guild.id, tournament_id)
        if not tournament:
            await ctx.respond("Tournament not found.", ephemeral=True)
            return
        
        success, message = await add_dummy_players(tournament, count)
        if success:
            await ctx.respond(message, ephemeral=True)
            from views.management import update_tournament_embeds
            await update_tournament_embeds(tournament, ctx.interaction)

    @bot.slash_command(name="clean_dummies", description="Remove all dummy players (Debug mode only)", guild_ids=[1286841607576092763])
    async def clean_dummies(ctx: discord.ApplicationContext, tournament_id: int):
        tournament = Tournament.load_tournament_by_id(ctx.guild.id, tournament_id)
        if not tournament:
            await ctx.respond("Tournament not found.", ephemeral=True)
            return
        
        removed = await clean_dummy_players(tournament)
        await ctx.respond(f"Removed {removed} dummy players.", ephemeral=True)

