import discord
from tournament import Tournament

# Check if the user has the admin role or is a server admin
async def check_tournament_admin(interaction: discord.Interaction, tournament: Tournament):          
    admin_role = discord.utils.get(interaction.guild.roles, name=f"({tournament.id}) Tournament Admin")

    if not interaction.user.guild_permissions.administrator and admin_role not in interaction.user.roles:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Failed. Only Tournament Admins have permission to perform this action.", ephemeral=True)
        else:
            # If the response is already sent, use followup
            await interaction.followup.send(f"Failed. Only Tournament Admins have permission to perform this action.", ephemeral=True)
        return False
    return True

# Function to move the reserve on the first index to the players list and then move all reserves 1 index up.
async def move_reserve_to_player(tournament: Tournament):
    if len(tournament.players) < tournament.player_cap and len(tournament.reserves) > 0:
        tournament.register_player(tournament.reserves[0])
        tournament.reserves.pop(0)
        tournament.save()
        return True
    return False