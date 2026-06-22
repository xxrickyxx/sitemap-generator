# Google Sitemap Generator Pro - miamai.it 🚀

Uno strumento completo e professionale per scansionare siti web e generare sitemap XML conformi ai requisiti di Google Search Console, con un'interfaccia grafica moderna (Web-based GUI) e un crawler asincrono multi-thread.

## 🌟 Funzionalità

- **Interfaccia Grafica Moderna (Dark Mode)**: Cruscotto responsive con statistiche in tempo reale (pagine in coda, velocità di scansione in URL/s, tempo trascorso) e log dettagliato della scansione.
- **Crawler Multi-Thread**: Algoritmo asincrono parallelo veloce che gestisce le richieste concorrenti ed esclude automaticamente link esterni, ancore (`#`) e risorse statiche (immagini, video, CSS, JS, PDF, zip, ecc.).
- **Suddivisione Automatica delle Sitemap**: Divide automaticamente l'elenco delle URL in più file sitemap (es. 5.000 URL per file come impostato di default) ed genera un file indice `sitemap_index.xml` che le raggruppa.
- **Selezione Range di URL (Nuovo)**: Consente di specificare un range preciso di link da esportare (es. da 5000 a 10000, da 10000 a 15000, ecc.) per gestire esportazioni parziali o aggiornamenti progressivi delle sitemap.
- **Zero Dipendenze Esterne**: Funziona direttamente con la libreria standard di Python (nessuna installazione di `pip install` richiesta).

---

## 📁 Struttura del Progetto

```
📁 sitemap-generator-google/
  ├── 🚀 Avvia Sitemap Generator.bat  ← Launcher doppio-clic per Windows
  ├── 🐍 sitemap_generator.py          ← Backend (Server HTTP + Crawler + XML Generator)
  ├── 📝 .gitignore                    ← File di configurazione Git
  └── 📁 ui/
      ├── index.html                   ← Pagina della Dashboard
      ├── index.css                    ← Stile premium dark mode
      └── index.js                     ← Logica di interazione e polling API
```

---

## 💻 Requisiti

- **Python 3.x** installato sul sistema.
- **Sistema Operativo**: Windows (per l'avvio rapido con file `.bat`), ma eseguibile anche su macOS e Linux avviando direttamente lo script Python.

---

## 🚀 Come Utilizzarlo

1. Fai doppio clic sul file **`Avvia Sitemap Generator.bat`**.
2. Il server si avvierà in automatico e aprirà la dashboard web nel tuo browser all'indirizzo:
   👉 **`http://localhost:8000`**
3. Inserisci i parametri desiderati nella dashboard:
   - **URL di Partenza**: `https://miamai.it` (o il sito che desideri scansionare).
   - **Limite URL per File**: Numero massimo di URL per ogni file sitemap (es. `5000`).
   - **Richieste Parallele**: Numero di connessioni concorrenti (es. `5` o `10`).
   - **Range URL (Opzionale)**: Specifica il range desiderato (es. da `1` a `5000` o da `5001` a `10000`).
4. Clicca su **"Avvia Scansione"**.
5. Al termine, clicca su **"Apri Cartella"** per accedere direttamente alla cartella `sitemaps/` contenente tutti i file XML pronti da caricare su Google Search Console!
