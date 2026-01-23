#!/usr/bin/env python3
"""
Tag Generator for index.js
===========================

Parses a Danbooru tag CSV export and injects updated tag data into index.js.
This updates VALID_BOORU_TAGS, TAG_ALIASES, BACKGROUND_TAGS, and CLOTHING_TAGS.

Usage:
    python3 tools/generate_tags.py [--csv PATH] [--threshold N] [--dry-run]

Arguments:
    --csv PATH       Path to danbooru CSV file (default: /home/gc/Downloads/TAGS/danbooru_2024-12-22_pt25-ia-dd.csv)
    --threshold N    Minimum post count for tag inclusion (default: 100)
    --dry-run        Print stats without modifying index.js

CSV Format (no header):
    tag_name,type,count,"alias1,alias2,..."

    - Column 0: tag name (e.g., "1girl", "blue_eyes")
    - Column 1: tag type (0=general, 1=artist, 3=copyright, 4=character, 5=meta)
    - Column 2: post count
    - Column 3: comma-separated aliases in quotes (optional)

    Only type-0 (general) tags are extracted.

What it modifies in index.js:
    - VALID_BOORU_TAGS: Set of all valid tags (type-0 with count >= threshold)
    - TAG_ALIASES: Object mapping alias strings to their canonical tag
    - BACKGROUND_TAGS: Curated subset of VALID_BOORU_TAGS for scene persistence
    - CLOTHING_TAGS: Curated subset of VALID_BOORU_TAGS for clothing persistence

    The script locates these by searching for their declaration patterns and
    replaces everything between the opening and closing delimiters.

Notes:
    - BACKGROUND_TAGS and CLOTHING_TAGS candidates are hardcoded in this script.
      Only candidates that exist in the generated VALID_BOORU_TAGS are included.
      To add new persistence tags, add them to the candidate lists in
      generate_background_tags() or generate_clothing_tags().
    - The script preserves all code before and after the tag data sections.
    - Tags are sorted alphabetically, 8 per line for VALID_BOORU_TAGS,
      6 per line for persistence tags.
"""

import csv
import sys
import argparse

DEFAULT_CSV = "/home/gc/Downloads/TAGS/danbooru_2024-12-22_pt25-ia-dd.csv"
INDEX_JS_PATH = "/home/gc/Github/Image-gen-kazuma/index.js"


def parse_csv(csv_path, threshold):
    """Parse the danbooru CSV and return type-0 tags with count >= threshold."""
    tags = {}  # tag_name -> {'count': int, 'aliases': [str]}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            tag_name = row[0]
            try:
                tag_type = int(row[1])
                tag_count = int(row[2])
            except (ValueError, IndexError):
                continue

            if tag_type != 0 or tag_count < threshold:
                continue

            aliases = []
            if len(row) >= 4 and row[3].strip():
                aliases = [a.strip() for a in row[3].split(',') if a.strip()]

            tags[tag_name] = {'count': tag_count, 'aliases': aliases}

    return tags


def escape_js_string(s):
    """Escape a string for use in a JS single-quoted string."""
    s = s.replace('\\', '\\\\')
    s = s.replace("'", "\\'")
    return s


def format_tags_set(tag_names):
    """Format tags as JavaScript Set entries, 8 per line."""
    sorted_tags = sorted(tag_names)
    lines = []
    for i in range(0, len(sorted_tags), 8):
        chunk = sorted_tags[i:i+8]
        entries = ", ".join(f"'{escape_js_string(t)}'" for t in chunk)
        lines.append(f"    {entries}")
    return lines


def format_aliases(aliases_dict):
    """Format aliases as JavaScript object entries, sorted alphabetically."""
    lines = []
    for alias in sorted(aliases_dict.keys()):
        canonical = aliases_dict[alias]
        lines.append(f"    '{escape_js_string(alias)}': '{escape_js_string(canonical)}'")
    return lines


def generate_background_tags(valid_tags):
    """
    Generate expanded BACKGROUND_TAGS.
    Only includes tags that exist in valid_tags.

    To add new background/scene tags, append them to the candidates list below.
    """
    candidates = [
        # Core indoor/outdoor
        'indoors', 'outdoors', 'bedroom', 'bathroom', 'kitchen', 'living_room', 'classroom',
        'hallway', 'rooftop', 'balcony', 'office', 'library', 'hospital', 'church', 'temple',
        'shrine', 'castle', 'dungeon', 'cave', 'ruins', 'alley', 'street', 'city', 'town',
        'village', 'park', 'garden', 'forest', 'jungle', 'mountain', 'hill', 'cliff',
        'beach', 'ocean', 'sea', 'lake', 'river', 'waterfall', 'pool', 'hot_spring',
        'desert', 'snow', 'field', 'meadow', 'farm', 'bridge', 'train', 'bus', 'car_interior',
        'space', 'underwater', 'sky', 'cloud', 'sunset', 'sunrise', 'night', 'day',
        'evening', 'morning', 'twilight', 'rain', 'snowing', 'fog', 'storm',
        'starry_sky', 'moonlight', 'sunlight', 'shade', 'dark', 'bright',
        'bed', 'couch', 'chair', 'desk', 'table', 'window', 'door', 'stairs',
        'cafe', 'restaurant', 'bar_(place)', 'shop', 'market', 'stadium', 'arena',
        'stage', 'gym', 'dojo', 'laboratory', 'prison', 'throne_room', 'tent', 'campfire',
        # Indoor locations
        'attic', 'basement', 'lobby', 'corridor', 'locker_room', 'closet', 'pantry',
        'laundry_room', 'greenhouse', 'garage', 'warehouse', 'factory', 'studio',
        'theater', 'cinema', 'museum', 'gallery', 'hotel_room', 'elevator', 'staircase',
        'auditorium', 'chapel', 'infirmary', 'changing_room', 'fitting_room',
        'cockpit', 'control_room', 'server_room', 'recording_studio',
        'hot_tub', 'sauna', 'onsen', 'spa',
        # Outdoor locations
        'highway', 'parking_lot', 'pier', 'dock', 'harbor', 'port', 'airport',
        'train_station', 'bus_stop', 'cemetery', 'graveyard', 'amusement_park',
        'zoo', 'aquarium', 'observatory', 'lighthouse', 'dam', 'canal',
        'swamp', 'marsh', 'bog', 'tundra', 'savanna', 'volcano', 'canyon',
        'valley', 'plateau', 'island', 'coast', 'shore', 'riverbank',
        'fountain', 'courtyard', 'plaza', 'alleyway', 'overpass', 'tunnel',
        'construction_site', 'junkyard', 'landfill', 'quarry', 'mine',
        'vineyard', 'orchard', 'rice_field', 'wheat_field',
        'playground', 'schoolyard', 'sports_field', 'track_and_field',
        'skating_rink', 'ski_resort', 'campsite', 'picnic',
        'crosswalk', 'sidewalk', 'road', 'path', 'trail',
        'flower_field', 'bamboo_forest', 'cherry_blossoms',
        'pagoda', 'mosque', 'cathedral', 'monastery', 'tower',
        'skyscraper', 'apartment', 'building', 'house', 'hut', 'cabin',
        'treehouse', 'gazebo', 'pavilion', 'veranda', 'porch', 'patio',
        'rooftop_garden', 'conservatory',
        # Weather/atmosphere
        'blizzard', 'hail', 'thunder', 'lightning', 'overcast', 'clear_sky',
        'mist', 'haze', 'dust', 'sandstorm', 'rainbow', 'aurora',
        'cloudy_sky', 'cloudy', 'rainy', 'windy', 'wind',
        'sunny', 'partly_cloudy', 'heavy_rain', 'drizzle',
        'snowflakes', 'snowstorm', 'typhoon', 'hurricane', 'tornado',
        'meteor', 'shooting_star', 'comet', 'eclipse',
        'dusk', 'dawn', 'midnight', 'noon', 'afternoon',
        'crescent_moon', 'full_moon', 'half_moon', 'new_moon',
        'sun', 'moon', 'stars', 'constellation',
        'autumn_leaves', 'falling_leaves', 'petals', 'falling_petals',
        'cherry_blossom_petals', 'snow_on_ground',
        # Lighting
        'candlelight', 'lantern', 'neon_lights', 'fluorescent',
        'spotlight', 'backlight', 'backlighting', 'dramatic_lighting',
        'rim_lighting', 'lens_flare', 'god_rays', 'crepuscular_rays',
        'soft_lighting', 'harsh_lighting', 'dim_lighting',
        'light_rays', 'light_beam', 'light_particles',
        'shadow', 'silhouette', 'reflection', 'glowing',
        'fire', 'bonfire', 'torch', 'lamp', 'chandelier',
        'streetlight', 'street_lamp', 'light_bulb',
        'fireflies', 'bioluminescence',
        # Furniture/features
        'fireplace', 'bookshelf', 'counter', 'sink', 'bathtub', 'shower',
        'mirror', 'curtain', 'curtains', 'rug', 'carpet', 'lamp',
        'sofa', 'armchair', 'bench', 'stool', 'throne',
        'altar', 'podium', 'lectern', 'blackboard', 'chalkboard', 'whiteboard',
        'television', 'computer', 'monitor', 'screen', 'projector',
        'piano', 'organ', 'fountain', 'statue', 'pillar', 'column',
        'arch', 'gate', 'fence', 'wall', 'ceiling', 'floor',
        'tile_floor', 'wooden_floor', 'tatami', 'futon',
        'clock', 'vase', 'painting_(object)', 'picture_frame',
        'shelf', 'drawer', 'cabinet', 'wardrobe', 'chest',
        'barrel', 'crate', 'box', 'basket',
        # Scenery/nature
        'tree', 'trees', 'bush', 'grass', 'moss', 'ivy',
        'flower', 'flowers', 'rose', 'sunflower', 'lily', 'lotus',
        'mushroom', 'coral', 'seaweed', 'kelp',
        'rock', 'boulder', 'pebble', 'sand', 'dirt', 'mud',
        'ice', 'icicle', 'glacier', 'iceberg',
        'lava', 'magma', 'geyser', 'hot_springs',
        'pond', 'stream', 'creek', 'rapids', 'tide_pool',
        'wave', 'waves', 'splash', 'ripple', 'foam',
        'cave_interior', 'stalactite', 'stalagmite',
        # Sky states
        'blue_sky', 'orange_sky', 'red_sky', 'purple_sky', 'pink_sky',
        'night_sky', 'gradient_sky',
        'horizon', 'cityscape', 'landscape', 'scenery',
        'nature', 'wilderness',
    ]
    return [t for t in candidates if t in valid_tags]


def generate_clothing_tags(valid_tags):
    """
    Generate expanded CLOTHING_TAGS.
    Only includes tags that exist in valid_tags.

    To add new clothing/accessory tags, append them to the candidates list below.
    """
    candidates = [
        # Core clothing
        'shirt', 't-shirt', 'dress_shirt', 'blouse', 'tank_top', 'crop_top', 'tube_top',
        'sweater', 'hoodie', 'cardigan', 'jacket', 'coat', 'blazer', 'vest',
        'dress', 'sundress', 'gown', 'wedding_dress', 'evening_gown', 'chinese_dress',
        'skirt', 'miniskirt', 'pleated_skirt', 'long_skirt',
        'pants', 'jeans', 'shorts', 'short_shorts', 'bike_shorts',
        'uniform', 'school_uniform', 'military_uniform', 'maid', 'nurse', 'police',
        'sailor_collar', 'serafuku',
        'bikini', 'swimsuit', 'one-piece_swimsuit', 'school_swimsuit',
        'kimono', 'yukata', 'japanese_clothes', 'chinese_clothes',
        'armor', 'cape', 'cloak', 'robe',
        'pajamas', 'nightgown', 'lingerie', 'underwear', 'bra', 'panties',
        'apron', 'overalls', 'bodysuit', 'jumpsuit', 'leotard',
        'necktie', 'bow', 'ribbon', 'scarf', 'gloves', 'hat', 'cap',
        'boots', 'shoes', 'sandals', 'high_heels', 'sneakers',
        'thighhighs', 'pantyhose', 'kneehighs', 'socks', 'stockings',
        'naked', 'nude', 'topless', 'bare_shoulders', 'bare_legs',
        'towel', 'towel_wrap', 'sports_bra', 'gym_uniform',
        # More tops
        'polo_shirt', 'hawaiian_shirt', 'flannel', 'turtleneck', 'halter_top',
        'bandeau', 'bustier', 'corset', 'camisole',
        'off-shoulder_shirt', 'sleeveless_shirt', 'cropped_shirt',
        'button-up_shirt', 'collared_shirt', 'open_shirt',
        'raglan_sleeves', 'puffy_sleeves', 'long_sleeves', 'short_sleeves',
        'sleeveless', 'strapless', 'backless_outfit', 'see-through',
        # More bottoms
        'cargo_pants', 'sweatpants', 'leggings', 'capri_pants',
        'harem_pants', 'pencil_skirt', 'a-line_skirt',
        'wrap_skirt', 'denim_shorts', 'gym_shorts',
        'high-waist_skirt', 'low-rise_pants', 'bell-bottoms',
        'micro_skirt', 'frilled_skirt', 'layered_skirt',
        'plaid_skirt', 'checkered_skirt', 'striped_skirt',
        'yoga_pants', 'track_pants', 'sweatshorts',
        # More dresses
        'cocktail_dress', 'ball_gown', 'shift_dress', 'wrap_dress',
        'slip_dress', 'maxi_dress', 'mini_dress',
        'strapless_dress', 'halterneck_dress', 'backless_dress',
        'mermaid_dress', 'princess_dress', 'lolita_fashion',
        'gothic_lolita', 'sweet_lolita', 'classic_lolita',
        'pinafore_dress', 'shirt_dress', 'summer_dress',
        'frilled_dress', 'layered_dress', 'high-low_dress',
        # More outerwear
        'parka', 'windbreaker', 'peacoat', 'trench_coat', 'denim_jacket',
        'leather_jacket', 'fur_coat', 'poncho', 'shawl', 'stole',
        'fur_trim', 'hood', 'hooded_jacket', 'rain_coat', 'lab_coat',
        'letterman_jacket', 'bomber_jacket', 'varsity_jacket',
        'suit', 'tuxedo', 'formal', 'business_suit',
        'track_jacket', 'anorak', 'overcoat',
        # More footwear
        'loafers', 'oxfords', 'pumps', 'stilettos', 'wedges',
        'platform_shoes', 'flip-flops', 'slippers', 'ballet_shoes',
        'combat_boots', 'riding_boots', 'thigh_boots', 'knee_boots',
        'ankle_boots', 'rain_boots', 'snow_boots',
        'mary_janes', 'school_shoes', 'dress_shoes',
        'barefoot', 'no_shoes', 'shoe_soles',
        'roller_skates', 'ice_skates', 'ski_boots',
        'geta', 'zouri', 'uwabaki', 'waraji',
        # Accessories
        'choker', 'necklace', 'pendant', 'bracelet', 'bangle',
        'earrings', 'ring', 'watch', 'wristwatch',
        'belt', 'suspenders', 'tie_clip', 'cufflinks', 'brooch',
        'hairpin', 'hair_clip', 'headband', 'hairband', 'tiara', 'crown',
        'hair_ribbon', 'hair_bow', 'hair_flower', 'hair_ornament',
        'scrunchie', 'ponytail_holder',
        'glasses', 'sunglasses', 'monocle', 'goggles',
        'mask', 'gas_mask', 'surgical_mask', 'face_mask',
        'bag', 'handbag', 'purse', 'backpack', 'messenger_bag',
        'satchel', 'briefcase', 'wallet', 'pouch',
        'umbrella', 'parasol', 'fan', 'folding_fan',
        'collar', 'dog_collar', 'chain', 'leash',
        'armband', 'armlet', 'anklet', 'leg_garter',
        'wristband', 'sweatband', 'bandana', 'bandanna',
        'pocket_watch', 'locket', 'amulet', 'talisman',
        'epaulettes', 'shoulder_pads', 'pauldrons',
        # Headwear
        'beret', 'beanie', 'fedora', 'top_hat', 'cowboy_hat',
        'sun_hat', 'straw_hat', 'witch_hat', 'wizard_hat',
        'santa_hat', 'party_hat', 'nurse_cap', 'chef_hat',
        'baseball_cap', 'visor', 'helmet', 'hard_hat',
        'veil', 'headdress', 'headpiece', 'maid_headdress',
        'animal_ears', 'cat_ears', 'dog_ears', 'fox_ears',
        'rabbit_ears', 'bunny_ears', 'wolf_ears', 'horse_ears',
        'fake_animal_ears', 'animal_ear_headphones',
        'halo', 'horns', 'antlers', 'ahoge',
        'hair_over_one_eye', 'bangs', 'side_bangs', 'blunt_bangs',
        # Underwear/swimwear
        'thong', 'g-string', 'boyshorts', 'briefs', 'boxers',
        'garter_belt', 'garter_straps', 'garters',
        'string_bikini', 'micro_bikini', 'sling_bikini',
        'monokini', 'tankini', 'competition_swimsuit',
        'bikini_top', 'bikini_bottom', 'swim_trunks',
        'side-tie_bikini', 'front-tie_bikini', 'bandeau_bikini',
        'highleg', 'highleg_leotard', 'highleg_swimsuit',
        'lowleg', 'lowleg_panties',
        'fundoshi', 'loincloth', 'sarong', 'pareo',
        'negligee', 'babydoll', 'chemise', 'teddy_(lingerie)',
        'corset', 'bustier', 'waist_cincher',
        # States/modifications
        'undressing', 'partially_clothed',
        'clothes_lift', 'shirt_lift', 'skirt_lift', 'dress_lift',
        'clothes_pull', 'shirt_pull', 'skirt_pull', 'pants_pull',
        'open_clothes', 'open_shirt', 'open_jacket', 'open_coat',
        'unbuttoned', 'unzipped', 'untied', 'loosened',
        'torn_clothes', 'torn_shirt', 'torn_dress', 'torn_pants',
        'wet_clothes', 'wet_shirt', 'wet_dress',
        'tight_clothes', 'tight_shirt', 'tight_dress', 'tight_pants',
        'oversized_clothes', 'oversized_shirt',
        'clothes_around_waist', 'jacket_around_waist',
        'off_shoulder', 'single_bare_shoulder',
        'rolled_up_sleeves', 'pushed_up_sleeves',
        'cross-laced_clothes', 'lace-up', 'lace_trim',
        'frills', 'frilled', 'ruffles', 'ruffled',
        'plaid', 'striped', 'polka_dot', 'checkered',
        'floral_print', 'camouflage', 'leopard_print', 'zebra_print',
        # Uniforms/costumes
        'cheerleader', 'bunny_girl', 'bunny_suit', 'playboy_bunny',
        'maid_apron', 'maid_dress', 'french_maid',
        'sailor_uniform', 'sailor_dress', 'sailor_shirt',
        'witch', 'witch_costume', 'angel', 'devil',
        'santa_costume', 'santa_dress', 'christmas_outfit',
        'halloween_costume', 'vampire', 'succubus',
        'pirate', 'cowgirl', 'cowboy',
        'flight_attendant', 'waitress', 'bartender',
        'firefighter', 'astronaut', 'pilot',
        'detective', 'spy', 'ninja', 'samurai',
        'gladiator', 'knight', 'paladin', 'ranger',
        'idol', 'idol_clothes', 'stage_outfit',
        'gym_leader', 'magical_girl', 'sailor_senshi_uniform',
        'plugsuit', 'pilot_suit', 'racing_suit',
        'track_suit', 'track_jacket', 'track_pants',
        'gym_shorts', 'gym_shirt', 'athletic_wear',
        'kendo_uniform', 'karate_gi', 'judo_gi',
        'ballet_outfit', 'tutu', 'dance_outfit',
        'cheerleader_uniform', 'tennis_uniform',
        'basketball_uniform', 'soccer_uniform', 'baseball_uniform',
        'volleyball_uniform', 'swimming_cap',
        # Garment details
        'zipper', 'button', 'buckle', 'clasp',
        'pocket', 'collar', 'lapel', 'cuff',
        'hem', 'seam', 'pleat', 'dart',
        'shoulder_strap', 'spaghetti_strap', 'halter',
        'drawstring', 'elastic', 'velcro',
        'embroidery', 'sequins', 'beading', 'rhinestone',
        'tassel', 'fringe', 'pompom',
        'hood_down', 'hood_up', 'zipper_pull_tab',
    ]
    return [t for t in candidates if t in valid_tags]


def main():
    parser = argparse.ArgumentParser(description='Generate tag data for index.js from Danbooru CSV')
    parser.add_argument('--csv', default=DEFAULT_CSV, help=f'Path to CSV file (default: {DEFAULT_CSV})')
    parser.add_argument('--threshold', type=int, default=100, help='Minimum post count (default: 100)')
    parser.add_argument('--dry-run', action='store_true', help='Print stats only, do not modify index.js')
    args = parser.parse_args()

    print(f"Parsing {args.csv} (threshold: {args.threshold})...", file=sys.stderr)
    tags = parse_csv(args.csv, args.threshold)
    print(f"Found {len(tags)} type-0 tags with {args.threshold}+ posts", file=sys.stderr)

    # Generate VALID_BOORU_TAGS
    tag_names = set(tags.keys())
    tags_lines = format_tags_set(tag_names)

    # Generate TAG_ALIASES
    aliases_dict = {}
    for tag_name, info in tags.items():
        for alias in info['aliases']:
            aliases_dict[alias] = tag_name

    print(f"Generated {len(aliases_dict)} alias mappings", file=sys.stderr)

    # Generate expanded persistence tags
    background_tags = generate_background_tags(tag_names)
    clothing_tags = generate_clothing_tags(tag_names)

    print(f"Background tags: {len(background_tags)} (validated against VALID_BOORU_TAGS)", file=sys.stderr)
    print(f"Clothing tags: {len(clothing_tags)} (validated against VALID_BOORU_TAGS)", file=sys.stderr)

    if args.dry_run:
        print("\n[DRY RUN] No changes written.", file=sys.stderr)
        return

    # Read original index.js
    with open(INDEX_JS_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find section markers dynamically
    valid_tags_start = None
    valid_tags_end = None
    bg_tags_start = None
    bg_tags_end = None
    cloth_tags_start = None
    cloth_tags_end = None
    aliases_start = None
    aliases_end = None

    for i, line in enumerate(lines):
        if "const VALID_BOORU_TAGS = new Set([" in line:
            valid_tags_start = i
        elif valid_tags_start is not None and valid_tags_end is None and line.strip() == "]);":
            valid_tags_end = i
        elif "const BACKGROUND_TAGS = new Set([" in line:
            bg_tags_start = i
        elif bg_tags_start is not None and bg_tags_end is None and line.strip() == "]);":
            bg_tags_end = i
        elif "const CLOTHING_TAGS = new Set([" in line:
            cloth_tags_start = i
        elif cloth_tags_start is not None and cloth_tags_end is None and line.strip() == "]);":
            cloth_tags_end = i
        elif "const TAG_ALIASES = {" in line:
            aliases_start = i
        elif aliases_start is not None and aliases_end is None and line.strip() == "};":
            aliases_end = i

    if None in [valid_tags_start, valid_tags_end, bg_tags_start, bg_tags_end,
                cloth_tags_start, cloth_tags_end, aliases_start, aliases_end]:
        print("ERROR: Could not find all section markers in index.js", file=sys.stderr)
        sys.exit(1)

    print(f"\nSection locations in index.js:", file=sys.stderr)
    print(f"  VALID_BOORU_TAGS: lines {valid_tags_start+1}-{valid_tags_end+1}", file=sys.stderr)
    print(f"  BACKGROUND_TAGS:  lines {bg_tags_start+1}-{bg_tags_end+1}", file=sys.stderr)
    print(f"  CLOTHING_TAGS:    lines {cloth_tags_start+1}-{cloth_tags_end+1}", file=sys.stderr)
    print(f"  TAG_ALIASES:      lines {aliases_start+1}-{aliases_end+1}", file=sys.stderr)

    # Build new file content
    new_lines = []

    # Everything before VALID_BOORU_TAGS comment (1 line before the Set declaration)
    comment_line = valid_tags_start - 1
    new_lines.extend(lines[:comment_line])

    # VALID_BOORU_TAGS
    new_lines.append(f"// Valid booru tags (extracted from danbooru dataset - category 0 tags with {args.threshold}+ posts)\n")
    new_lines.append("const VALID_BOORU_TAGS = new Set([\n")
    for i, tl in enumerate(tags_lines):
        if i < len(tags_lines) - 1:
            new_lines.append(tl + ",\n")
        else:
            new_lines.append(tl + "\n")
    new_lines.append("]);\n")
    new_lines.append("\n")

    # BACKGROUND_TAGS
    new_lines.append("// Scene Persistence: Background/setting tags (curated subset of VALID_BOORU_TAGS)\n")
    new_lines.append("const BACKGROUND_TAGS = new Set([\n")
    for i in range(0, len(background_tags), 6):
        chunk = background_tags[i:i+6]
        entries = ", ".join(f"'{escape_js_string(t)}'" for t in chunk)
        if i + 6 < len(background_tags):
            new_lines.append(f"    {entries},\n")
        else:
            new_lines.append(f"    {entries}\n")
    new_lines.append("]);\n")
    new_lines.append("\n")

    # CLOTHING_TAGS
    new_lines.append("// Scene Persistence: Clothing tags (curated subset of VALID_BOORU_TAGS)\n")
    new_lines.append("const CLOTHING_TAGS = new Set([\n")
    for i in range(0, len(clothing_tags), 6):
        chunk = clothing_tags[i:i+6]
        entries = ", ".join(f"'{escape_js_string(t)}'" for t in chunk)
        if i + 6 < len(clothing_tags):
            new_lines.append(f"    {entries},\n")
        else:
            new_lines.append(f"    {entries}\n")
    new_lines.append("]);\n")
    new_lines.append("\n")

    # TAG_ALIASES
    new_lines.append("// Alias corrections (extracted from danbooru - maps common variations to canonical booru tags)\n")
    new_lines.append("const TAG_ALIASES = {\n")
    alias_lines = format_aliases(aliases_dict)
    for i, al in enumerate(alias_lines):
        if i < len(alias_lines) - 1:
            new_lines.append(al + ",\n")
        else:
            new_lines.append(al + "\n")
    new_lines.append("};\n")

    # Everything after TAG_ALIASES closing brace
    new_lines.extend(lines[aliases_end + 1:])

    # Write output
    with open(INDEX_JS_PATH, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"\nDone! Written {len(new_lines)} lines to {INDEX_JS_PATH}", file=sys.stderr)
    print(f"  VALID_BOORU_TAGS: {len(tag_names)} entries", file=sys.stderr)
    print(f"  TAG_ALIASES:      {len(aliases_dict)} entries", file=sys.stderr)
    print(f"  BACKGROUND_TAGS:  {len(background_tags)} entries", file=sys.stderr)
    print(f"  CLOTHING_TAGS:    {len(clothing_tags)} entries", file=sys.stderr)


if __name__ == "__main__":
    main()
