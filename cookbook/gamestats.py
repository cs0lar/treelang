import logging
from typing import List
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("gamestats", debug=False)


@mcp.tool()
def get_players(platform: str) -> List[int]:
    """
    Get the players ID of all the players using the given gaming platform
    """
    logging.info(f"Getting players for platform: {platform}")
    if platform == "Steam":
        return [11, 8, 41]
    elif platform == "Sony":
        return [8, 21, 221, 42, 532]
    else:
        raise ValueError(f"Unknown platform: {platform}")


@mcp.tool()
def get_game_stats(game: str, feature: str, players: List[int]) -> List[int]:
    """
    Get statistics for a given video game title for the given list of player IDs.
    Valid values for `feature` are: `hours_played`, `quests`, `bounties`, `energy`, `level`
    """
    logging.info(
        f"Getting stats for game: {game}, feature: {feature}, players: {players}"
    )
    if game == "Destiny 2" and feature == "hours_played":
        if len(players) and all([(item in players) for item in [11, 8, 41]]):
            return [12, 43, 15, 22, 132, 42, 54, 32, 11]
        return []

    if game == "Doom" and feature == "hours_played":
        if len(players) and all([(item in players) for item in [8, 21, 221, 42, 532]]):
            return [1, 54, 233, 231, 64, 722, 43, 7, 23, 89, 23, 222]
        return []


@mcp.tool()
def average(values: List[int]) -> float:
    """
    Calculate the average of a list of integers
    """
    logging.info(f"Calculating average of {values}")
    if len(values) == 0:
        return 0.0
    return sum(values) / len(values)


if __name__ == "__main__":
    mcp.run(transport="stdio")
