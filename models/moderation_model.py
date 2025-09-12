"""
A simple, rule-based AI model for content moderation.
This is a placeholder and can be replaced with a sophisticated ML model later.
"""

# A list of keywords that might indicate inappropriate content.
# This list should be expanded and handled with care in a real application.
BANNED_WORDS = [
    "abbo", "abo", "abuse", "addict", "addicts", "africa", "african", "alla", "allah", "allahu akbar",
    "anal", "anus", "arab", "arabs", "argie", "aryan", "ass", "asses", "assface", "asshole", "assholes",
    "asslick", "asslicker", "assrammer", "asswipe", "b1tch", "bampot", "basta", "bastard", "bastards",
    "beaner", "beastial", "beastiality", "beatch", "beater", "beeyotch", "biatch", "bigot", "bigots",
    "bitch", "bitcher", "bitchin", "bitching", "bitchy", "blow job", "blowjob", "bollocks", "bollox",
    "boner", "boob", "boobs", "boong", "botha", "bozo", "bullshit", "camel jockey", "carpet muncher",
    "chav", "chink", "chinky", "choad", "chode", "clit", "clitoris", "clits", "clitty", "cocaine",
    "cock", "cockface", "cockhead", "cockjockey", "cockmunch", "cockmuncher", "cocks", "cocksuck",
    "cocksucker", "cocksucking", "coochie", "coochy", "coon", "cooner", "crack", "cracker", "crackwhore",
    "crap", "crappy", "cum", "cumming", "cumshot", "cumstain", "cunilingus", "cunnilingus", "cunt",
    "cunt-ass", "cuntface", "cuntlicker", "cunts", "dago", "damn", "damned", "damnit", "dego", "devil",
    "dick", "dick-ish", "dickbag", "dicked", "dickhead", "dickish", "dickweed", "dicks", "dike", "dildo",
    "dildos", "dink", "dipshit", "dix", "dope", "douche", "douchebag", "duche", "dyke", "ejaculate",
    "ejaculated", "ejaculates", "ejaculating", "ejaculation", "enema", "fag", "faggot", "faggots",
    "fagtard", "fanny", "fart", "fatass", "fatso", "fellatio", "feltch", "ficken", "figgot", "fingerbang",
    "fingerfucked", "fingerfucker", "fingerfuckers", "fistfuck", "fistfucked", "fistfucker", "flamer",
    "fuck", "fuck-off", "fuckass", "fucked", "fucker", "fuckers", "fuckface", "fuckhead", "fuckin",
    "fucking", "fuckme", "fucknugget", "fuckoff", "fucks", "fuckstick", "fucktard", "fuckup", "fuckwad",
    "fuckwit", "fudgepacker", "ganja", "gash", "gay", "gaylord", "gays", "god-damned", "goddamn",
    "goddamned", "gook", "gringo", "guido", "gyp", "gypsy", "hadji", "haji", "half-breed", "halfbreed",
    "hard on", "heeb", "hell", "heroin", "herp", "herpes", "hick", "hillbilly", "hiv", "ho", "ho-bag",
    "hoar", "hoe", "hoer", "homo", "homosexual", "honkey", "honky", "hooker", "hore", "horny", "humping",
    "hussy", "hymen", "inbred", "incest", "injun", "jigaboo", "jiggaboo", "jism", "jiz", "jizm", "jizz",
    "juggalo", "juggalo", "junkie", "junky", "kike", "kikes", "kill", "killer", "killing", "klan",
    "kooch", "kooches", "kootch", "kraut", "kyke", "labia", "lardass", "lesbo", "lesbos", "lez", "lezbian",
    "lezbians", "lezbo", "lezbos", "lezz", "lezzie", "lezzies", "lezzy", "lsd", "lust", "marijuana",
    "masterbate", "masturbate", "meth", "mick", "milf", "molest", "mothafucka", "mothafucker", "motherfucker",
    "motherfucking", "muff", "muffdiver", "murder", "murderer", "nazi", "nazis", "negro", "nig", "niga",
    "nigar", "niger", "nigga", "niggar", "niggars", "nigger", "niggers", "nigguh", "nigs", "nonce",
    "opium", "orgy", "paki", "paky", "pansy", "paedo", "paedophile", "paddy", "pecker", "peckerhead",
    "pedo", "pedophile", "penis", "perv", "pervert", "pikey", "pimp", "piss", "pissed", "pissed off",
    "pisser", "pissflaps", "polack", "pillock", "poon", "poontang", "porn", "porno", "prick", "prostitute",
    "punani", "punany", "punny", "pussy", "pussyeater", "pussylips", "pussylicker", "pussys", "puto",
    "queaf", "queef", "queer", "queers", "raghead", "rape", "raped", "raper", "rapist", "redneck", "reefer",
    "retard", "retarded", "rube", "satan", "scag", "scank", "scat", "schizo", "schlong", "screw", "scrote",
    "scrotum", "semen", "sex", "shag", "she-male", "shemale", "shit", "shit-ass", "shitass", "shitbag",
    "shitcunt", "shitdick", "shite", "shiteater", "shitface", "shithead", "shithole", "shithouse", "shits",
    "shitt", "shitted", "shitter", "shitting", "shitty", "skag", "skank", "slag", "slut", "slut-ass",
    "slutbag", "slutty", "sluts", "smack", "smegma", "snatch", "sod off", "sodom", "sodomy", "spic",
    "spick", "spik", "spunk", "squarehead", "stfu", "stoned", "sudaca", "suicide", "swastika", "tard",
    "terrydactyl", "teste", "testicle", "testicles", "thicko", "thot", "thot", "thundercunt", "tit",
    "tits", "titty", "tittyfuck", "tittyfucker", "toke", "tramp", "tranny", "trany", "troon", "turd",
    "twat", "twatlips", "twatwaffle", "unclefucker", "urine", "vag", "vagina", "viagra", "vomit", "wank",
    "wanker", "wankjob", "wanky", "weed", "wetback", "whop", "whore", "whore-ass", "whorebag", "whoreface",
    "whores", "wigger", "wop", "wtf", "x-rated", "xxx", "bhenchod", "madarchod", "gandu", "chutiya", "randi", "bhosda", "bhosdike",
    "gaand", "jhaat", "choot", "loda", "lawda", "harami", "kutta", "kamina",
    "saala", "saali", "behenchod", "bakchod", "chutiye", "chut", "madar",
    "bhadwa", "hijda", "chakke", "lund", "tatte", "jhant", "suar", "ullu ka pattha"
]

def check_content(text_content):
    """
    Checks a given text for inappropriate content based on a keyword list.

    Args:
        text_content (str): The text of the post or comment to check.

    Returns:
        dict: A dictionary containing the moderation decision.
              - "is_flagged": (bool) True if content is deemed inappropriate, False otherwise.
              - "reason": (str) A brief reason for the decision.
    """
    text_lower = text_content.lower()
    
    for word in BANNED_WORDS:
        if word in text_lower:
            return {
                "is_flagged": True,
                "reason": f"Content flagged for containing sensitive keyword: '{word}'"
            }
            
    return {
        "is_flagged": False,
        "reason": "Content passed moderation."
    }

# --- Example Usage (for testing the model directly) ---
if __name__ == '__main__':
    clean_text = "I think the new library hours are fantastic."
    flagged_text = "This is a post containing a profanity1 word."

    clean_result = check_content(clean_text)
    flagged_result = check_content(flagged_text)

    print(f"Checking clean text: {clean_result}")
    # Expected output: {'is_flagged': False, 'reason': 'Content passed moderation.'}

    print(f"Checking flagged text: {flagged_result}")
    # Expected output: {'is_flagged': True, 'reason': "Content flagged for containing sensitive keyword: 'profanity1'"}
