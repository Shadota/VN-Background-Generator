#!/usr/bin/env python3
"""
Tag Generator for index.js
===========================

Parses a Danbooru tag CSV export and injects updated tag data into index.js.
This updates VALID_BOORU_TAGS, TAG_ALIASES, BACKGROUND_TAGS, LOCATION_TAGS,
ATMOSPHERE_TAGS, and TIME_TAGS.

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
    - LOCATION_TAGS: Curated subset for location persistence
    - ATMOSPHERE_TAGS: Curated subset for atmosphere/lighting persistence
    - TIME_TAGS: Curated subset for time-of-day persistence

    The script locates these by searching for their declaration patterns and
    replaces everything between the opening and closing delimiters.

Notes:
    - All persistence tag candidates are hardcoded in this script.
      Only candidates that exist in the generated VALID_BOORU_TAGS are included.
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


def generate_location_tags(valid_tags):
    """
    Generate LOCATION_TAGS — places and structures.
    Only includes tags that exist in valid_tags.
    """
    candidates = [
        'indoors', 'outdoors', 'bedroom', 'bathroom', 'kitchen', 'living_room',
        'classroom', 'hallway', 'rooftop', 'balcony', 'office', 'library',
        'hospital', 'church', 'temple', 'shrine', 'castle', 'dungeon',
        'cave', 'ruins', 'alley', 'street', 'city', 'town',
        'village', 'park', 'garden', 'forest', 'jungle', 'mountain',
        'hill', 'cliff', 'beach', 'ocean', 'lake', 'river',
        'waterfall', 'pool', 'desert', 'field', 'meadow', 'farm',
        'bridge', 'train', 'bus', 'car_interior', 'space', 'underwater',
        'cafe', 'restaurant', 'bar_(place)', 'shop', 'market', 'stadium',
        'arena', 'stage', 'gym', 'dojo', 'laboratory', 'prison',
        'throne_room', 'tent', 'campfire', 'locker_room', 'closet', 'greenhouse',
        'garage', 'warehouse', 'factory', 'studio', 'theater', 'museum',
        'hotel_room', 'elevator', 'infirmary', 'changing_room', 'fitting_room',
        'cockpit', 'recording_studio', 'sauna', 'onsen', 'highway', 'parking_lot',
        'pier', 'dock', 'harbor', 'airport', 'train_station', 'bus_stop',
        'graveyard', 'amusement_park', 'zoo', 'aquarium', 'lighthouse', 'canal',
        'volcano', 'canyon', 'valley', 'island', 'shore', 'riverbank',
        'fountain', 'overpass', 'tunnel', 'construction_site', 'junkyard',
        'wheat_field', 'playground', 'track_and_field', 'skating_rink', 'picnic',
        'crosswalk', 'sidewalk', 'road', 'path', 'flower_field', 'bamboo_forest',
        'cherry_blossoms', 'pagoda', 'cathedral', 'tower', 'skyscraper', 'apartment',
        'building', 'house', 'hut', 'cabin', 'treehouse', 'gazebo',
        'veranda', 'porch', 'conservatory', 'cave_interior', 'ballroom',
        'courtyard', 'plaza', 'monastery', 'corridor', 'lobby',
    ]
    return [t for t in candidates if t in valid_tags]


def generate_atmosphere_tags(valid_tags):
    """
    Generate ATMOSPHERE_TAGS — weather, lighting, and atmospheric effects.
    Only includes tags that exist in valid_tags.
    """
    candidates = [
        'rain', 'snowing', 'fog', 'storm', 'wind', 'blizzard', 'thunder',
        'lightning', 'overcast', 'clear_sky', 'dust', 'sandstorm', 'rainbow',
        'aurora', 'cloudy_sky', 'cloudy', 'snowflakes', 'snowstorm', 'tornado',
        'meteor', 'shooting_star', 'comet', 'eclipse',
        'candlelight', 'lantern', 'neon_lights', 'spotlight', 'backlighting',
        'lens_flare', 'dim_lighting', 'light_rays', 'light_particles',
        'shadow', 'silhouette', 'reflection', 'glowing', 'fire', 'bonfire',
        'torch', 'lamp', 'chandelier', 'light_bulb', 'fireflies', 'bioluminescence',
        'dappled_sunlight', 'sunbeam', 'sun_glare', 'hanging_light', 'stage_lights',
        'underlighting', 'depth_of_field', 'dark_clouds',
        'petals', 'falling_petals', 'falling_leaves', 'autumn_leaves',
        'cherry_blossom_petals', 'snow',
        'dark', 'bright', 'shade', 'moonlight', 'sunlight',
    ]
    return [t for t in candidates if t in valid_tags]


def generate_time_tags(valid_tags):
    """
    Generate TIME_TAGS — time of day and sky states.
    Only includes tags that exist in valid_tags.
    """
    candidates = [
        'sunset', 'sunrise', 'night', 'day', 'evening', 'morning',
        'twilight', 'dusk', 'dawn', 'midnight', 'noon', 'afternoon',
        'starry_sky', 'night_sky', 'blue_sky', 'orange_sky', 'red_sky',
        'purple_sky', 'pink_sky', 'gradient_sky',
        'crescent_moon', 'full_moon', 'half_moon', 'sun', 'moon',
        'constellation', 'golden_hour',
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
    location_tags = generate_location_tags(tag_names)
    atmosphere_tags = generate_atmosphere_tags(tag_names)
    time_tags = generate_time_tags(tag_names)

    print(f"Background tags: {len(background_tags)} (validated against VALID_BOORU_TAGS)", file=sys.stderr)
    print(f"Location tags: {len(location_tags)} (validated against VALID_BOORU_TAGS)", file=sys.stderr)
    print(f"Atmosphere tags: {len(atmosphere_tags)} (validated against VALID_BOORU_TAGS)", file=sys.stderr)
    print(f"Time tags: {len(time_tags)} (validated against VALID_BOORU_TAGS)", file=sys.stderr)

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
    loc_tags_start = None
    loc_tags_end = None
    atm_tags_start = None
    atm_tags_end = None
    time_tags_start = None
    time_tags_end = None
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
        elif "const LOCATION_TAGS = new Set([" in line:
            loc_tags_start = i
        elif loc_tags_start is not None and loc_tags_end is None and line.strip() == "]);":
            loc_tags_end = i
        elif "const ATMOSPHERE_TAGS = new Set([" in line:
            atm_tags_start = i
        elif atm_tags_start is not None and atm_tags_end is None and line.strip() == "]);":
            atm_tags_end = i
        elif "const TIME_TAGS = new Set([" in line:
            time_tags_start = i
        elif time_tags_start is not None and time_tags_end is None and line.strip() == "]);":
            time_tags_end = i
        elif "const TAG_ALIASES = {" in line:
            aliases_start = i
        elif aliases_start is not None and aliases_end is None and line.strip() == "};":
            aliases_end = i

    required = [valid_tags_start, valid_tags_end, bg_tags_start, bg_tags_end,
                loc_tags_start, loc_tags_end, atm_tags_start, atm_tags_end,
                time_tags_start, time_tags_end, aliases_start, aliases_end]
    if None in required:
        print("ERROR: Could not find all section markers in index.js", file=sys.stderr)
        print(f"  VALID_BOORU_TAGS: {valid_tags_start}-{valid_tags_end}", file=sys.stderr)
        print(f"  BACKGROUND_TAGS:  {bg_tags_start}-{bg_tags_end}", file=sys.stderr)
        print(f"  LOCATION_TAGS:    {loc_tags_start}-{loc_tags_end}", file=sys.stderr)
        print(f"  ATMOSPHERE_TAGS:  {atm_tags_start}-{atm_tags_end}", file=sys.stderr)
        print(f"  TIME_TAGS:        {time_tags_start}-{time_tags_end}", file=sys.stderr)
        print(f"  TAG_ALIASES:      {aliases_start}-{aliases_end}", file=sys.stderr)
        sys.exit(1)

    print(f"\nSection locations in index.js:", file=sys.stderr)
    print(f"  VALID_BOORU_TAGS: lines {valid_tags_start+1}-{valid_tags_end+1}", file=sys.stderr)
    print(f"  BACKGROUND_TAGS:  lines {bg_tags_start+1}-{bg_tags_end+1}", file=sys.stderr)
    print(f"  LOCATION_TAGS:    lines {loc_tags_start+1}-{loc_tags_end+1}", file=sys.stderr)
    print(f"  ATMOSPHERE_TAGS:  lines {atm_tags_start+1}-{atm_tags_end+1}", file=sys.stderr)
    print(f"  TIME_TAGS:        lines {time_tags_start+1}-{time_tags_end+1}", file=sys.stderr)
    print(f"  TAG_ALIASES:      lines {aliases_start+1}-{aliases_end+1}", file=sys.stderr)

    def format_persistence_set(tags_list):
        """Format persistence tags, 6 per line."""
        result = []
        for i in range(0, len(tags_list), 6):
            chunk = tags_list[i:i+6]
            entries = ", ".join(f"'{escape_js_string(t)}'" for t in chunk)
            if i + 6 < len(tags_list):
                result.append(f"    {entries},\n")
            else:
                result.append(f"    {entries}\n")
        return result

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
    new_lines.extend(format_persistence_set(background_tags))
    new_lines.append("]);\n")
    new_lines.append("\n")

    # LOCATION_TAGS
    new_lines.append("// Scene Persistence: Location tags (curated subset of VALID_BOORU_TAGS)\n")
    new_lines.append("const LOCATION_TAGS = new Set([\n")
    new_lines.extend(format_persistence_set(location_tags))
    new_lines.append("]);\n")
    new_lines.append("\n")

    # ATMOSPHERE_TAGS
    new_lines.append("// Scene Persistence: Atmosphere/lighting tags (curated subset of VALID_BOORU_TAGS)\n")
    new_lines.append("const ATMOSPHERE_TAGS = new Set([\n")
    new_lines.extend(format_persistence_set(atmosphere_tags))
    new_lines.append("]);\n")
    new_lines.append("\n")

    # TIME_TAGS
    new_lines.append("// Scene Persistence: Time-of-day tags (curated subset of VALID_BOORU_TAGS)\n")
    new_lines.append("const TIME_TAGS = new Set([\n")
    new_lines.extend(format_persistence_set(time_tags))
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
    print(f"  LOCATION_TAGS:    {len(location_tags)} entries", file=sys.stderr)
    print(f"  ATMOSPHERE_TAGS:  {len(atmosphere_tags)} entries", file=sys.stderr)
    print(f"  TIME_TAGS:        {len(time_tags)} entries", file=sys.stderr)


if __name__ == "__main__":
    main()
