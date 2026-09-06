from datetime import datetime

DATE_FORMAT = "%d-%m-%Y"
TIME_FORMAT = "%H:%M"

def transform(matches):

    transformed_matches = []

    for match in matches:

        # Keep only finished matches
        if not match["matchIsFinished"]:
            continue

        # Find the final score
        final_result = next(
            (
                result
                for result in match["matchResults"]
                if result["resultTypeKind"] == "After90Minutes"
            ),
            None
        )

        # Skip finished matches without a valid final result
        if final_result is None:
            continue

        home_goals = final_result["pointsTeam1"]
        away_goals = final_result["pointsTeam2"]

        # Outcome from the home team's perspective: H home win, A away win, D draw
        if home_goals > away_goals:
            result = "Home win"
        elif home_goals < away_goals:
            result = "Away win"
        else:
            result = "Draw"

        # Kickoff is split into a readable date and time, both UTC
        kickoff = datetime.fromisoformat(match["matchDateTimeUTC"])

        transformed_match = {
            "match_date": kickoff.strftime(DATE_FORMAT),
            "kickoff_time": kickoff.strftime(TIME_FORMAT),
            "matchweek": match["group"]["groupOrderID"],
            "home_team": match["team1"]["teamName"],
            "away_team": match["team2"]["teamName"],
            "home_goals": home_goals,
            "away_goals": away_goals,
            "result": result,
            "total_goals": home_goals + away_goals,
            "goal_difference": home_goals - away_goals,
            "last_update": match["lastUpdateDateTime"]
        }

        # Append the transformed match to the list
        transformed_matches.append(transformed_match)

    print(f"Transformed {len(transformed_matches)} finished matches")

    return transformed_matches
