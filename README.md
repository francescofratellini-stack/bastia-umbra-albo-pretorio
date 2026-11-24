# Scarica documenti dall'Albo Pretorio di Bastia Umbra

Piccola app web in italiano per cercare link pubblici ad atti/allegati dall'Albo Pretorio comunale e scaricarli in un archivio ZIP.

## Avvio in locale

Richiede Python 3.10 o successivo.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
streamlit run app.py
```

L'app si apre nel browser. Conferma l'URL proposto e premi **Cerca documenti**; poi filtra/seleziona i documenti e prepara lo ZIP.

Pagina preimpostata: https://bastiaumbra.halleyweb.it/c054002/zf/index.php/atti-amministrativi/albo

## Note

- Per sicurezza, le richieste sono limitate al dominio `bastiaumbra.halleyweb.it`.
- La scansione parte dalla pagina indicata e prova a seguire fino a 30 link a pagine di dettaglio; non effettua scansioni massive del sito.
- Limiti: 30 MB per file e 100 MB complessivi per archivio.
- Il portale può cambiare URL, struttura HTML o modalità di accesso; se la ricerca non trova risultati, consulta il sito ufficiale e aggiorna l'URL.
- Gli atti firmati digitalmente (ad esempio `.p7m`) possono richiedere software idoneo per la verifica e la lettura.
- Usare il servizio nel rispetto delle condizioni del portale e delle norme sulla protezione dei dati e sul riutilizzo dei documenti.
