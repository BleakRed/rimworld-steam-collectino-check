import requests
import xml.etree.ElementTree as ET
import os

# --- CONFIG ---
# your RimWorld mods config file path (mine is like this because linux)
modsconfig_path = "~/.config/unity3d/Ludeon Studios/RimWorld by Ludeon Studios/Config/ModsConfig.xml"
# Your RimWorld steam workshop path (mine is like this because linux)
workshop_dir = "~/.local/share/Steam/steamapps/workshop/content/294100"
# your Steam collection ID
# https://steamcommunity.com/sharedfiles/filedetails/?id=1234567
collection_id = "Steam_Collection_ID"

modsconfig_path = os.path.expanduser(modsconfig_path)
workshop_dir = os.path.expanduser(workshop_dir)

# --- Vanilla packageIds to ignore ---
vanilla_mods = {
    "ludeon.rimworld",
    "ludeon.rimworld.royalty",
    "ludeon.rimworld.ideology",
    "ludeon.rimworld.biotech",
    "ludeon.rimworld.anomaly",
    "ludeon.rimworld.odyssey"
}

# --- Parse ModsConfig.xml (original) ---
tree = ET.parse(modsconfig_path)
root = tree.getroot()
active_mods = [mod.text.lower() for mod in root.findall("./activeMods/li")]
active_mods_filtered = [m for m in active_mods if m not in vanilla_mods]

print(f"📑 Total active mods in ModsConfig.xml (excluding Core & DLCs): {len(active_mods_filtered)}")

# --- Build packageId → workshopID map from local Workshop folders ---
packageid_to_workshopid = {}

for wid in os.listdir(workshop_dir):
    about_path = os.path.join(workshop_dir, wid, "About", "About.xml")
    if os.path.isfile(about_path):
        try:
            about_tree = ET.parse(about_path)
            about_root = about_tree.getroot()
            pkgid_elem = about_root.find("packageId")
            if pkgid_elem is not None:
                packageid_to_workshopid[pkgid_elem.text.lower()] = wid
        except Exception:
            continue

print(f"🔎 Found {len(packageid_to_workshopid)} packageId mappings from local Workshop folder")

# --- Fetch Steam Collection (copy) ---
url = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"
payload = {"collectioncount": 1, "publishedfileids[0]": collection_id}
resp = requests.post(url, data=payload)
data = resp.json()

collection_mods = []
if "response" in data and "collectiondetails" in data["response"]:
    for child in data["response"]["collectiondetails"][0]["children"]:
        collection_mods.append(child["publishedfileid"])

print(f"📦 Mods in Steam Collection: {len(collection_mods)}")

# --- Compare ---
missing_in_copy = []   # ModsConfig but not in collection
present_in_both = []   # ModsConfig + collection
extra_in_copy = []     # Collection but not in ModsConfig

for pkgid in active_mods_filtered:
    wid = packageid_to_workshopid.get(pkgid)
    if wid:
        if wid in collection_mods:
            present_in_both.append((pkgid, wid))
        else:
            missing_in_copy.append((pkgid, wid))
    else:
        missing_in_copy.append((pkgid, "❌ no workshop ID found (maybe local mod?)"))

# Reverse: check extras
for wid in collection_mods:
    # Find the packageId from mapping
    pkgid_match = [pid for pid, pwid in packageid_to_workshopid.items() if pwid == wid]
    pkgid = pkgid_match[0] if pkgid_match else None
    if pkgid not in active_mods_filtered:
        extra_in_copy.append((pkgid if pkgid else "❓ unknown packageId", wid))

# --- Resolve names ---
def get_mod_names(ids):
    if not ids:
        return {}
    url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
    payload = {"itemcount": len(ids)}
    for i, mid in enumerate(ids):
        payload[f"publishedfileids[{i}]"] = mid
    resp = requests.post(url, data=payload)
    data = resp.json()
    results = {}
    for d in data.get("response", {}).get("publishedfiledetails", []):
        results[d["publishedfileid"]] = d.get("title", "Unknown Title")
    return results

all_ids = [wid for _, wid in present_in_both + missing_in_copy + extra_in_copy if wid.isdigit()]
id_to_name = get_mod_names(all_ids)

# --- Print results ---

# uncomment the below to see the mods
# print("\n✅ Present in BOTH ModsConfig (original) and Collection (copy):")
# for pkgid, wid in present_in_both:
#     print(f"{id_to_name.get(wid, 'Unknown')} ({pkgid} / {wid})")

print("\n❌ In ModsConfig (original) but MISSING from Collection (copy):")
for pkgid, wid in missing_in_copy:
    if wid.isdigit():
        print(f"{id_to_name.get(wid, 'Unknown')} ({pkgid} / {wid})")
    else:
        print(f"{pkgid} ({wid})")

print("\n⚠️ EXTRA in Collection (copy) but NOT in ModsConfig (original):")
for pkgid, wid in extra_in_copy:
    print(f"{id_to_name.get(wid, 'Unknown')} ({pkgid} / {wid})")

if not missing_in_copy and not extra_in_copy:
    print("\n🎉 ModsConfig and Collection are perfectly in sync!")
