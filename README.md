# summer-workshop
Níže je návrh snímku/notebookové buňky, kterou vložíte do JupyterLab (či jiného notebooku) jako Úvod k REST API. Obsahuje stručné vysvětlení a ukázky 4 základních metod s knihovnou requests.

markdown
Copy
Edit
## Úvod k REST API

**HTTP metody**  
- `GET`  – načtení dat  
- `POST` – vytvoření nového záznamu  
- `PUT`  – aktualizace existujícího záznamu  
- `DELETE` – odstranění záznamu  

**Základní hlavičky**  
```http
Content-Type: application/json  
Authorization: Bearer <YOUR_TOKEN>
python
Copy
Edit
# 1) Import a základní nastavení
import requests
API_BASE = "https://inveniordm.web.cern.ch/api/records"
TOKEN    = "VAŠE_PERSONAL_ACCESS_TOKEN"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}

# 2) GET – načtení seznamu záznamů
resp = requests.get(API_BASE, headers=headers)
print("GET /records →", resp.status_code)
print(resp.json())  # ukázka výstupu: metadata, id, links…

# 3) POST – vytvoření nového záznamu
new_record = {
    "metadata": {
        "title": "Demo z Jupyteru",
        "publication_date": "2025-07-10",
        "creators": [
            {
                "person_or_org": {"type": "personal", "given_name": "Jana", "family_name": "Novák"},
                "role": {"id": "other"}
            }
        ],
        "resource_type": {"id": "dataset"}
    }
}
resp = requests.post(API_BASE, json=new_record, headers=headers)
print("POST /records →", resp.status_code)
record_id = resp.json().get("id")
print("Vytvořen record ID:", record_id)

# 4) PUT – aktualizace existujícího záznamu (např. přejmenování)
update_data = {
    "metadata": {
        "title": "Demo z Jupyteru – upravený název"
    }
}
url = f"{API_BASE}/{record_id}/draft"
resp = requests.put(url, json=update_data, headers=headers)
print("PUT /records/{id}/draft →", resp.status_code)

# 5) DELETE – smazání záznamu
url = f"{API_BASE}/{record_id}"
resp = requests.delete(url, headers=headers)
print("DELETE /records/{id} →", resp.status_code)
Poznámka:

Nahraďte API_BASE a TOKEN svými hodnotami.

V příkladu pro PUT a DELETE se předpokládá, že záznam je ve stavu „draft“ a že máte právo jej smazat.

Tento úvodní snímek/nebo blok kódu dává účastníkům přehled nejčastěji používaných operací a připraví je na další hands-on části workshopu.
