import requests
import json
import time

def fetch_quran_taisirul_quran():
    # Base URL for the Quran Foundation Content API v4
    base_url = "https://api.quran.com/api/v4"
    
    # Resource ID 161 corresponds to the Taisirul Quran Bengali translation
    translation_id = 161
    
    all_verses = []
    
    # Loop through all 114 Chapters (Surahs)
    for chapter in range(1, 115):
        print(f"Fetching Surah {chapter}...")
        page = 1
        total_pages = 1
        
        # Paginate through the verses in the current Surah
        while page <= total_pages:
            url = f"{base_url}/verses/by_chapter/{chapter}"
            
            params = {
                "translations": translation_id,
                "fields": "text_uthmani", # Requests the Arabic text
                "page": page,
                "per_page": 50  # Maximum records allowed per API call
            }
            
            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                # Parse the verses from the response
                verses = data.get("verses", [])
                for verse in verses:
                    verse_key = verse.get("verse_key")
                    arabic_text = verse.get("text_uthmani")
                    
                    # Extract the translation text safely
                    translations = verse.get("translations", [])
                    bengali_translation = translations[0].get("text") if translations else ""
                    
                    all_verses.append({
                        "verse_key": verse_key,
                        "arabic_text": arabic_text,
                        "bengali_translation": bengali_translation
                    })
                
                # Update pagination variables to continue the loop if necessary
                pagination = data.get("pagination", {})
                total_pages = pagination.get("total_pages", 1)
                page += 1
                
                # Pause briefly to avoid hitting rate limits
                time.sleep(0.1)
                
            except requests.exceptions.RequestException as e:
                print(f"Error fetching chapter {chapter}, page {page}: {e}")
                break

    # Save the consolidated data into a local JSON file
    output_file = "quran_taisirul_bengali.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_verses, f, ensure_ascii=False, indent=4)
        
    print(f"Successfully saved {len(all_verses)} verses to {output_file}")

if __name__ == "__main__":
    fetch_quran_taisirul_quran()