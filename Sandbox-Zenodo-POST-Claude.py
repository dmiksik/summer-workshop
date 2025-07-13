# %% [markdown]
# # Workshop: Vložení datasetu do Zenodo přes REST API
# 
# Tento notebook demonstruje celý proces vytvoření záznamu a vložení dat do sandbox.zenodo.org
# 
# ## Potřebné knihovny a nastavení

# %%
import requests
import json
import yaml
import os
from pathlib import Path
from datetime import datetime
import time

# Nastavení pro sandbox Zenodo
ZENODO_API_URL = "https://sandbox.zenodo.org/api"
ACCESS_TOKEN = "your_access_token_here"  # Nahraďte svým access tokenem

# Hlavičky pro API požadavky
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {ACCESS_TOKEN}'
}

print("🔧 Nastavení API připraveno")
print(f"API URL: {ZENODO_API_URL}")
print(f"Token nastaven: {'✓' if ACCESS_TOKEN != 'your_access_token_here' else '✗'}")

# %% [markdown]
# ## Krok 1: Načtení metadat ze YAML souboru

# %%
# Načteme metadata z YAML souboru
yaml_file = "record_test.yaml"

try:
    with open(yaml_file, 'r', encoding='utf-8') as f:
        metadata_yaml = yaml.safe_load(f)
    
    print("📄 YAML metadata úspěšně načtena:")
    print(f"Název: {metadata_yaml['title']}")
    print(f"Datum publikace: {metadata_yaml['publication_date']}")
    print(f"Typ zdroje: {metadata_yaml['resource_type']}")
    print(f"Počet autorů: {len(metadata_yaml['creators'])}")
    print(f"Jazyk: {metadata_yaml['language']['title']}")
    print(f"Licence: {metadata_yaml['license']['id']}")
    
    # Zobrazíme i další pole pokud existují
    if 'subjects' in metadata_yaml:
        print(f"Subjects: {len(metadata_yaml['subjects'])} položek")
    if 'contributors' in metadata_yaml:
        print(f"Contributors: {len(metadata_yaml['contributors'])} osob")
    if 'communities' in metadata_yaml:
        print(f"Communities: {len(metadata_yaml['communities'])} komunit")
    if 'funding' in metadata_yaml:
        print(f"Funding: {len(metadata_yaml['funding'])} grantů")
    
except FileNotFoundError:
    print(f"❌ Soubor {yaml_file} nebyl nalezen!")
    print("Vytvoříme testovací metadata...")
    
    # Fallback testovací data
    metadata_yaml = {
        'title': 'Ukázkový dataset pro workshop',
        'publication_date': '2025-07-15',
        'resource_type': 'dataset',
        'creators': [
            {
                'given_name': 'Jan',
                'family_name': 'Novák',
                'orcid': '0000-0001-2345-6789',
                'affiliation_text': 'Masarykova univerzita'
            }
        ],
        'description': 'Krátký popis datasetu pro workshop',
        'keywords': ['machine learning', 'workshop', 'demo'],
        'language': {'id': 'cs', 'title': 'Čeština'},
        'license': {'id': 'cc-by-4.0'}
    }

# %% [markdown]
# ## Krok 2: Transformace metadat do formátu Zenodo

# %%
def convert_yaml_to_zenodo(yaml_data):
    """Konvertuje YAML metadata do formátu požadovaného Zenodo API"""
    
    # Konverze data do string formátu (pokud je to date objekt)
    pub_date = yaml_data['publication_date']
    if hasattr(pub_date, 'strftime'):
        pub_date = pub_date.strftime('%Y-%m-%d')
    else:
        pub_date = str(pub_date)
    
    # Základní metadata
    zenodo_metadata = {
        'title': yaml_data['title'],
        'upload_type': 'dataset',
        'description': yaml_data.get('description', ''),
        'publication_date': pub_date,
        'language': yaml_data['language']['id']
    }
    
    # Autoři
    creators = []
    for creator in yaml_data.get('creators', []):
        zenodo_creator = {
            'name': f"{creator['family_name']}, {creator['given_name']}"
        }
        if 'orcid' in creator:
            zenodo_creator['orcid'] = creator['orcid']
        if 'affiliation_text' in creator:
            zenodo_creator['affiliation'] = creator['affiliation_text']
        creators.append(zenodo_creator)
    
    zenodo_metadata['creators'] = creators
    
    # Klíčová slova
    if 'keywords' in yaml_data:
        zenodo_metadata['keywords'] = yaml_data['keywords']
    
    # Předměty/subjects z kontrolovaného slovníku
    if 'subjects' in yaml_data:
        subjects = []
        for subject in yaml_data['subjects']:
            subject_entry = {
                'term': subject['term'],
                'identifier': subject['identifier']
            }
            # scheme se automaticky detekuje, ale můžeme ho poslat
            if 'scheme' in subject:
                subject_entry['scheme'] = subject['scheme']
            subjects.append(subject_entry)
        zenodo_metadata['subjects'] = subjects
    
    # Licence
    if 'license' in yaml_data:
        zenodo_metadata['license'] = yaml_data['license']['id']
    
    # Contributors (přispěvatelé)
    if 'contributors' in yaml_data:
        contributors = []
        for contributor in yaml_data['contributors']:
            zenodo_contributor = {
                'name': contributor['name'],
                'type': contributor['type']
            }
            if 'affiliation' in contributor:
                zenodo_contributor['affiliation'] = contributor['affiliation']
            if 'orcid' in contributor:
                zenodo_contributor['orcid'] = contributor['orcid']
            contributors.append(zenodo_contributor)
        zenodo_metadata['contributors'] = contributors
    
    # Communities (komunity)
    if 'communities' in yaml_data:
        communities = []
        for community in yaml_data['communities']:
            if isinstance(community, dict) and 'id' in community:
                communities.append({'identifier': community['id']})
            elif isinstance(community, str):
                communities.append({'identifier': community})
        if communities:
            zenodo_metadata['communities'] = communities
    
    # Financování - správný formát podle Zenodo API dokumentace
    if 'funding' in yaml_data:
        grants = []
        for fund in yaml_data['funding']:
            # Pokud má grant_id, použijeme ho
            if 'grant_id' in fund:
                grant_id = str(fund['grant_id'])
                # Pokud má funder_identifier, použijeme DOI-prefixed formát (doporučený)
                if 'funder_identifier' in fund and fund['funder_identifier'].startswith('10.13039/'):
                    grant_id = f"{fund['funder_identifier']}::{grant_id}"
                grants.append({'id': grant_id})
            # Alternativně pokud má award_number a je to EC grant
            elif 'award_number' in fund and 'funder_name' in fund:
                if 'Evropsk' in fund['funder_name'] or 'European' in fund['funder_name']:
                    # Pokusíme se extrahovat číslo grantu z award_number
                    award_num = fund['award_number'].replace('GA', '').replace('-', '')
                    if award_num.isdigit():
                        grants.append({'id': award_num})
        
        if grants:
            zenodo_metadata['grants'] = grants
    
    # Související identifikátory - pouze DOI
    if 'related_identifiers' in yaml_data:
        related_identifiers = []
        for rel_id in yaml_data['related_identifiers']:
            # Filtrujeme pouze DOI nebo berme všechny pokud scheme není definováno
            if 'scheme' not in rel_id or rel_id['scheme'] == 'doi':
                related_identifiers.append({
                    'identifier': rel_id['identifier'],
                    'relation': rel_id['relation_type']
                    # 'scheme' se neposílá - Zenodo ho automaticky detekuje z formátu
                })
        if related_identifiers:
            zenodo_metadata['related_identifiers'] = related_identifiers
    
    # Ujistíme se, že description není prázdný
    if not zenodo_metadata['description']:
        zenodo_metadata['description'] = f"Dataset: {yaml_data['title']}"
    
    return zenodo_metadata

# Konvertujeme metadata
zenodo_metadata = convert_yaml_to_zenodo(metadata_yaml)

print("🔄 Metadata konvertována do formátu Zenodo:")
print(f"📋 Odesílaná pole: {list(zenodo_metadata.keys())}")
try:
    print(json.dumps(zenodo_metadata, indent=2, ensure_ascii=False))
except TypeError as e:
    print(f"❌ Chyba při serializaci JSON: {e}")
    print("📋 Metadata (bez JSON formátování):")
    for key, value in zenodo_metadata.items():
        print(f"  {key}: {value} (typ: {type(value).__name__})")

# %% [markdown]
# ## Krok 3: Vytvoření nového záznamu (deposition)

# %%
def create_deposition():
    """Vytvoří nový záznam v Zenodo"""
    
    url = f"{ZENODO_API_URL}/deposit/depositions"
    
    print(f"📤 Odesíláme požadavek na: {url}")
    print(f"Hlavičky: {headers}")
    
    response = requests.post(url, headers=headers, json={})
    
    print(f"📥 Odpověď ze serveru:")
    print(f"Status kód: {response.status_code}")
    
    if response.status_code == 201:
        deposition = response.json()
        print("✅ Záznam úspěšně vytvořen!")
        print(f"ID záznamu: {deposition['id']}")
        print(f"Bucket URL: {deposition['links']['bucket']}")
        print(f"Publish URL: {deposition['links']['publish']}")
        return deposition
    else:
        print("❌ Chyba při vytváření záznamu:")
        print(f"Chyba: {response.text}")
        return None

# Vytvoříme nový záznam
deposition = create_deposition()

if deposition:
    deposition_id = deposition['id']
    bucket_url = deposition['links']['bucket']
    publish_url = deposition['links']['publish']
    
    print(f"\n📝 Záznam vytvořen s ID: {deposition_id}")

# %% [markdown]
# ## Krok 4: Aktualizace metadat záznamu

# %%
def validate_zenodo_metadata(metadata):
    """Validuje metadata před odesláním do Zenodo"""
    
    required_fields = ['title', 'upload_type', 'description', 'creators']
    missing_fields = []
    
    for field in required_fields:
        if field not in metadata or not metadata[field]:
            missing_fields.append(field)
    
    if missing_fields:
        print(f"❌ Chybí povinná pole: {missing_fields}")
        return False
    
    # Kontrola autorů
    if not isinstance(metadata['creators'], list) or len(metadata['creators']) == 0:
        print("❌ Pole 'creators' musí být neprázdný seznam")
        return False
    
    for i, creator in enumerate(metadata['creators']):
        if 'name' not in creator or not creator['name']:
            print(f"❌ Autor {i+1} nemá vyplněné jméno")
            return False
    
    # Kontrola upload_type
    valid_upload_types = ['publication', 'poster', 'presentation', 'dataset', 'image', 'video', 'software', 'lesson', 'physicalobject', 'other']
    if metadata['upload_type'] not in valid_upload_types:
        print(f"❌ Neplatný upload_type: {metadata['upload_type']}")
        print(f"Platné hodnoty: {valid_upload_types}")
        return False
    
    print("✅ Metadata prošla validací")
    return True

def update_metadata(deposition_id, metadata):
    """Aktualizuje metadata záznamu"""
    
    # Nejprve validujeme metadata
    if not validate_zenodo_metadata(metadata):
        return None
    
    url = f"{ZENODO_API_URL}/deposit/depositions/{deposition_id}"
    
    data = {'metadata': metadata}
    
    print(f"📤 Aktualizujeme metadata pro záznam {deposition_id}")
    print(f"URL: {url}")
    print("Odesílaná metadata:")
    print(f"📋 Pole: {list(metadata.keys())}")
    try:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Chyba při zobrazení JSON: {e}")
        print("Metadata bez JSON formátu:")
        for key, value in metadata.items():
            print(f"  {key}: {value}")
    
    response = requests.put(url, headers=headers, json=data)
    
    print(f"\n📥 Odpověď ze serveru:")
    print(f"Status kód: {response.status_code}")
    
    if response.status_code == 200:
        updated_deposition = response.json()
        print("✅ Metadata úspěšně aktualizována!")
        print(f"Nový název: {updated_deposition['metadata']['title']}")
        
        # Bezpečné zobrazení autorů
        creators = updated_deposition['metadata'].get('creators', [])
        author_names = []
        for creator in creators:
            if 'name' in creator:
                author_names.append(creator['name'])
            elif 'given_name' in creator and 'family_name' in creator:
                author_names.append(f"{creator['family_name']}, {creator['given_name']}")
            else:
                author_names.append("Neznámý autor")
        
        print(f"Autoři: {author_names}")
        return updated_deposition
    else:
        print("❌ Chyba při aktualizaci metadat:")
        print(f"Chyba: {response.text}")
        print("\n🔍 Diagnostika:")
        print(f"Content-Type hlavičky: {response.headers.get('content-type', 'N/A')}")
        
        # Pokusíme se parsovat JSON odpověď
        try:
            error_data = response.json()
            if 'errors' in error_data:
                print("Detaily chyb:")
                for error in error_data['errors']:
                    print(f"  - {error}")
        except:
            print("Nepodařilo se parsovat JSON odpověď")
        
        return None

# Aktualizujeme metadata pouze pokud máme vytvořený záznam
if 'deposition_id' in locals():
    print("🔍 Testujeme postupně různé varianty metadat...")
    
    # Zkusíme nejprve pouze základní metadata
    basic_metadata = {
        'title': zenodo_metadata['title'],
        'upload_type': 'dataset',
        'description': zenodo_metadata['description'],
        'creators': zenodo_metadata['creators']
    }
    
    print("\n1️⃣ Zkouším pouze základní metadata:")
    updated_deposition = update_metadata(deposition_id, basic_metadata)
    
    if updated_deposition:
        print("✅ Základní metadata fungují! Zkusíme přidat další pole...")
        
        # Přidáme postupně další pole
        extended_metadata = basic_metadata.copy()
        extended_metadata['language'] = zenodo_metadata['language']
        extended_metadata['keywords'] = zenodo_metadata['keywords']
        extended_metadata['license'] = zenodo_metadata['license']
        
        print("\n2️⃣ Zkouším s language, keywords a license:")
        updated_deposition = update_metadata(deposition_id, extended_metadata)
        
        if updated_deposition:
            print("✅ Rozšířená metadata fungují! Zkusíme přidat grants...")
            
            # Přidáme grants se správným formátem
            full_metadata = extended_metadata.copy()
            if 'grants' in zenodo_metadata:
                full_metadata['grants'] = zenodo_metadata['grants']
                print(f"📋 Grants k přidání: {zenodo_metadata['grants']}")
            
            print("\n3️⃣ Zkouším s grants:")
            updated_deposition = update_metadata(deposition_id, full_metadata)
            
            if updated_deposition:
                print("✅ Metadata s grants fungují! Zkusíme přidat všechna zbývající pole...")
                
                # Přidáme všechna zbývající pole z konvertovaných metadata
                complete_metadata = full_metadata.copy()
                
                # Přidáme pole pouze pokud existují v zenodo_metadata
                additional_fields = ['related_identifiers', 'subjects', 'contributors', 'communities']
                for field in additional_fields:
                    if field in zenodo_metadata:
                        complete_metadata[field] = zenodo_metadata[field]
                        if isinstance(zenodo_metadata[field], list):
                            print(f"📋 Přidávám {field}: {len(zenodo_metadata[field])} položek")
                        else:
                            print(f"📋 Přidávám {field}: {zenodo_metadata[field]}")
                
                print(f"\n4️⃣ Zkouším kompletní metadata s poli: {list(complete_metadata.keys())}")
                updated_deposition = update_metadata(deposition_id, complete_metadata)
    else:
        print("❌ Ani základní metadata nefungují. Zkusíme minimální verzi...")
        
        # Zkusíme úplně minimální metadata
        minimal_metadata = {
            'title': 'Test Dataset',
            'upload_type': 'dataset',
            'description': 'Test description',
            'creators': [{'name': 'Test, User'}]
        }
        
        print("\n🔧 Zkouším minimální metadata:")
        updated_deposition = update_metadata(deposition_id, minimal_metadata)

# %% [markdown]
# ## Krok 5: Vytvoření ukázkových dat pro upload

# %%
def create_sample_data():
    """Vytvoří ukázkové soubory pro demonstraci uploadu"""
    
    # Vytvoříme adresář pro data
    data_dir = Path("sample_data")
    data_dir.mkdir(exist_ok=True)
    
    # Vytvoříme ukázkový CSV soubor
    csv_content = """id,name,value,category
1,Sample A,10.5,machine_learning
2,Sample B,15.2,image_classification
3,Sample C,8.7,shiba_inu
4,Sample D,12.3,machine_learning
5,Sample E,9.8,image_classification"""
    
    csv_file = data_dir / "sample_dataset.csv"
    with open(csv_file, 'w', encoding='utf-8') as f:
        f.write(csv_content)
    
    # Vytvoříme README soubor
    readme_content = """# Ukázkový dataset pro workshop

## Popis
Tento dataset obsahuje ukázková data pro demonstraci procesu vložení do Zenodo.

## Obsah
- sample_dataset.csv: Hlavní datový soubor
- README.md: Tento popis

## Použití
Dataset je určen pro vzdělávací účely v rámci workshopu.

## Licence
CC BY 4.0
"""
    
    readme_file = data_dir / "README.md"
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    files_to_upload = [csv_file, readme_file]
    
    print("📁 Ukázková data vytvořena:")
    for file_path in files_to_upload:
        file_size = file_path.stat().st_size
        print(f"  - {file_path.name}: {file_size} bytů")
    
    return files_to_upload

# Vytvoříme ukázková data
sample_files = create_sample_data()

# %% [markdown]
# ## Krok 6: Upload souborů

# %%
def upload_file(bucket_url, file_path):
    """Nahraje soubor do Zenodo záznamu"""
    
    filename = file_path.name
    upload_url = f"{bucket_url}/{filename}"
    
    print(f"📤 Nahrávám soubor: {filename}")
    print(f"URL: {upload_url}")
    print(f"Velikost: {file_path.stat().st_size} bytů")
    
    # Připravíme hlavičky pro upload (bez Content-Type pro binární data)
    upload_headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }
    
    with open(file_path, 'rb') as f:
        response = requests.put(upload_url, headers=upload_headers, data=f)
    
    print(f"📥 Odpověď ze serveru:")
    print(f"Status kód: {response.status_code}")
    
    if response.status_code in [200, 201]:  # 200 nebo 201 jsou oba úspěšné
        file_info = response.json()
        print(f"✅ Soubor {filename} úspěšně nahrán!")
        print(f"Velikost na serveru: {file_info['size']} bytů")
        print(f"MIME type: {file_info['mimetype']}")
        print(f"Kontrolní součet: {file_info['checksum']}")
        return file_info
    else:
        print(f"❌ Chyba při nahrávání souboru {filename}:")
        print(f"Chyba: {response.text}")
        return None

# Nahrajeme všechny soubory
uploaded_files = []
if 'bucket_url' in locals():
    for file_path in sample_files:
        file_info = upload_file(bucket_url, file_path)
        if file_info:
            uploaded_files.append(file_info)
        time.sleep(1)  # Krátká pauza mezi uploady

print(f"\n📊 Celkem nahráno {len(uploaded_files)} souborů")

# %% [markdown]
# ## Krok 7: Kontrola stavu záznamu před publikováním

# %%
def get_deposition_status(deposition_id):
    """Získá aktuální stav záznamu"""
    
    url = f"{ZENODO_API_URL}/deposit/depositions/{deposition_id}"
    
    print(f"📋 Kontroluji stav záznamu {deposition_id}")
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        deposition = response.json()
        print("✅ Stav záznamu:")
        print(f"Název: {deposition['metadata']['title']}")
        print(f"Stav: {deposition['state']}")
        print(f"Počet souborů: {len(deposition['files'])}")
        print(f"Publikováno: {'Ano' if deposition['submitted'] else 'Ne'}")
        
        print("\n📎 Připojené soubory:")
        for file_info in deposition['files']:
            print(f"  - {file_info['filename']}: {file_info['filesize']} bytů")
        
        # Zobrazíme také klíčová metadata
        metadata = deposition['metadata']
        print(f"\n📋 Metadata:")
        print(f"  - Autoři: {len(metadata.get('creators', []))}")
        print(f"  - Klíčová slova: {len(metadata.get('keywords', []))}")
        if 'subjects' in metadata:
            print(f"  - Subjects: {len(metadata['subjects'])}")
        if 'contributors' in metadata:
            print(f"  - Contributors: {len(metadata['contributors'])}")
        if 'grants' in metadata:
            print(f"  - Grants: {len(metadata['grants'])}")
        
        return deposition
    else:
        print("❌ Chyba při získávání stavu:")
        print(f"Chyba: {response.text}")
        return None

# Zkontrolujeme stav záznamu
if 'deposition_id' in locals():
    current_deposition = get_deposition_status(deposition_id)

# %% [markdown]
# ## Krok 8: Publikování záznamu (volitelné)

# %%
def publish_deposition(deposition_id, confirm=False):
    """Publikuje záznam - POZOR: Tato akce je nevratná!"""
    
    if not confirm:
        print("⚠️  VAROVÁNÍ: Publikování záznamu je nevratná akce!")
        print("💡 Pro skutečné publikování nastavte parametr confirm=True")
        print("🔍 V sandbox prostředí můžete záznam bezpečně publikovat pro testování")
        return None
    
    url = f"{ZENODO_API_URL}/deposit/depositions/{deposition_id}/actions/publish"
    
    print(f"📢 Publikuji záznam {deposition_id}")
    print(f"URL: {url}")
    
    response = requests.post(url, headers=headers)
    
    print(f"📥 Odpověď ze serveru:")
    print(f"Status kód: {response.status_code}")
    
    if response.status_code == 202:
        published_record = response.json()
        print("🎉 Záznam úspěšně publikován!")
        print(f"DOI: {published_record['doi']}")
        print(f"URL záznamu: {published_record['links']['record_html']}")
        return published_record
    else:
        print("❌ Chyba při publikování:")
        print(f"Chyba: {response.text}")
        return None

# Ukážeme možnost publikování a skutečně publikujme (pokud uživatel chce)
print("📢 Publikování záznamu:")
if 'deposition_id' in locals():
    print(f"Záznam {deposition_id} je připraven k publikování.")
    print("⚠️  POZOR: Publikování je nevratná akce!")
    print()
    print("Pro publikování spusťte:")
    print(f"published_record = publish_deposition({deposition_id}, confirm=True)")
    print()
    
    # Automaticky publikujeme pro workshop (v sandbox prostředí je to bezpečné)
    print("🎓 Pro workshop automaticky publikujeme záznam...")
    published_record = publish_deposition(deposition_id, confirm=True)
    
    if published_record:
        print("\n🎉 ZÁZNAM ÚSPĚŠNĚ PUBLIKOVÁN!")
        print(f"DOI: {published_record.get('doi', 'N/A')}")
        if 'links' in published_record and 'record_html' in published_record['links']:
            print(f"URL: {published_record['links']['record_html']}")
else:
    print("❌ Záznam nebyl vytvořen - nelze publikovat")

# %% [markdown]
# ## Diagnostika communities - proč se nevložila

# %%
def search_communities(query="", size=20):
    """Vyhledá komunity v Zenodo"""
    
    url = f"{ZENODO_API_URL}/communities"
    params = {
        'size': size
    }
    if query:
        params['q'] = query
    
    print(f"🔍 Vyhledávám komunity...")
    print(f"URL: {url}")
    print(f"Parametry: {params}")
    
    response = requests.get(url, params=params)
    
    print(f"📥 Odpověď ze serveru:")
    print(f"Status kód: {response.status_code}")
    
    if response.status_code == 200:
        communities_data = response.json()
        communities = communities_data.get('hits', {}).get('hits', [])
        total = communities_data.get('hits', {}).get('total', 0)
        
        print(f"✅ Nalezeno {total} komunit (zobrazeno prvních {len(communities)}):")
        
        for community in communities:
            comm_id = community.get('id', 'N/A')
            title = community.get('metadata', {}).get('title', 'Bez názvu')
            description = community.get('metadata', {}).get('description', '')
            
            print(f"  📋 ID: {comm_id}")
            print(f"     Název: {title}")
            if description and len(description) > 100:
                description = description[:100] + "..."
            print(f"     Popis: {description}")
            print()
        
        return communities
    else:
        print(f"❌ Chyba při vyhledávání komunit:")
        print(f"Chyba: {response.text}")
        return []

def check_community_exists(community_id):
    """Zkontroluje zda komunita existuje"""
    
    url = f"{ZENODO_API_URL}/communities/{community_id}"
    
    print(f"🔍 Kontroluji existenci komunity: {community_id}")
    
    response = requests.get(url)
    
    if response.status_code == 200:
        community = response.json()
        print(f"✅ Komunita '{community_id}' existuje!")
        print(f"Název: {community.get('metadata', {}).get('title', 'N/A')}")
        return True
    elif response.status_code == 404:
        print(f"❌ Komunita '{community_id}' neexistuje!")
        return False
    else:
        print(f"❓ Chyba při kontrole komunity: {response.status_code}")
        print(f"Odpověď: {response.text}")
        return False

# Zkontrolujeme vaši komunitu z YAML
yaml_communities = metadata_yaml.get('communities', [])
if yaml_communities:
    print("🔍 KONTROLA KOMUNIT Z YAML:")
    print("=" * 40)
    
    for community in yaml_communities:
        comm_id = community.get('id') if isinstance(community, dict) else community
        print(f"\nKontroluje komunitu: {comm_id}")
        exists = check_community_exists(comm_id)
        
        if not exists:
            print(f"💡 Zkusíme vyhledat podobné komunity...")
            similar_communities = search_communities(query=comm_id, size=5)

# Vyhledejme workshop komunity
print("\n🎓 WORKSHOP KOMUNITY:")
print("=" * 30)
workshop_communities = search_communities(query="workshop", size=10)

# %% [markdown]
# ## Shrnutí workshopu

# %%
print("🎯 SHRNUTÍ WORKSHOPU")
print("=" * 50)

if 'deposition_id' in locals():
    print(f"✅ Záznam vytvořen: ID {deposition_id}")
    print(f"✅ Metadata aktualizována: {zenodo_metadata['title']}")
    print(f"✅ Soubory nahrány: {len(uploaded_files)}")
    print(f"📋 Stav záznamu: Připraven k publikování")
    
    print(f"\n🔗 Odkazy:")
    print(f"Sandbox záznam: https://sandbox.zenodo.org/deposit/{deposition_id}")
    
    print(f"\n📊 Zpracovaná metadata:")
    for field in zenodo_metadata.keys():
        if isinstance(zenodo_metadata[field], list):
            print(f"  - {field}: {len(zenodo_metadata[field])} položek")
        else:
            print(f"  - {field}: ✓")
    
else:
    print("❌ Záznam nebyl vytvořen - zkontrolujte ACCESS_TOKEN")

print(f"\n📚 Naučili jste se:")
print("• Jak načíst metadata z YAML")
print("• Jak konvertovat metadata do formátu Zenodo")
print("• Jak vytvořit nový záznam přes API")
print("• Jak nahrát soubory")
print("• Jak publikovat záznam")
print("• Jak řešit problematická pole (grants, subjects, contributors)")

print(f"\n🔧 Pro vlastní použití:")
print("1. Získejte access token na https://sandbox.zenodo.org/account/settings/applications/tokens/new/")
print("2. Nahraďte 'your_access_token_here' svým tokenem")
print("3. Pro produkční použití změňte URL na 'https://zenodo.org/api'")

# %% [markdown]
# ## Dodatečné utility funkce

# %%
def list_my_depositions():
    """Zobrazí seznam všech mých záznamů"""
    
    url = f"{ZENODO_API_URL}/deposit/depositions"
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        depositions = response.json()
        print(f"📋 Máte {len(depositions)} záznamů:")
        
        for dep in depositions:
            status = "Publikováno" if dep['submitted'] else "Koncept"
            print(f"  - ID {dep['id']}: {dep['metadata']['title']} ({status})")
            
        return depositions
    else:
        print("❌ Chyba při získávání seznamu:")
        print(f"Chyba: {response.text}")
        return []

def delete_deposition(deposition_id):
    """Smaže nepublikovaný záznam"""
    
    url = f"{ZENODO_API_URL}/deposit/depositions/{deposition_id}"
    
    response = requests.delete(url, headers=headers)
    
    if response.status_code == 204:
        print(f"✅ Záznam {deposition_id} byl smazán")
        return True
    else:
        print(f"❌ Chyba při mazání záznamu {deposition_id}:")
        print(f"Chyba: {response.text}")
        return False

# Ukázka utility funkcí
print("\n🛠️  UTILITY FUNKCE:")
print("• list_my_depositions() - zobrazí všechny vaše záznamy")
print("• delete_deposition(id) - smaže nepublikovaný záznam")
print("• get_deposition_status(id) - zobrazí detaily záznamu")

# Zavolejte například:
# my_depositions = list_my_depositions()