# NewTimes.news editorial guide: English edition

This guide applies to every story in the English edition (`content/en/`, published at `newtimes.news/en/`). It follows the same criteria as the Spanish edition (`redaccion/GUIA.md`): accuracy, attribution and service to the reader. Where something is not covered here, the Spanish guide and common journalistic sense apply.

## 1. What we publish

General-interest news for **English-speaking readers in Spain and abroad**: Spain explained for people who do not follow Spanish media, plus world news, business, society, science and health, technology, culture and sport.

The English edition is **not a translation** of the Spanish edition. It has its own selection of stories and its own texts. It may cover the same event as the Spanish edition, but the piece is written from scratch for this audience (more context about Spain, less about things only Spanish readers need).

Every hour **2 to 4 stories** are published, only if there are new facts that justify them. One solid story is better than four weak ones. If nothing new and relevant has happened, nothing is published.

### Selection criteria
1. New facts from the last few hours, confirmed by at least one source on the list.
2. Impact on many people or clear public relevance, with priority to Spain and Europe.
3. Not already published in the English edition: always check `python3 redaccion/recientes.py 48 en` before choosing. If a published story has important new developments, write a new piece on the development.
4. Variety: no more than 2 pieces from the same section per hour.

### Never published
- Rumours, unconfirmed leaks, unverified viral content.
- Offers, products, giveaways, sponsored or affiliate content.
- Our own opinion, editorials or value judgements. Opinions only appear attributed to whoever expressed them.
- Horoscopes, health advice without scientific backing.
- Information about private individuals that is not in the public interest. No identified victims unless the authorities or families have made their identity public.
- Morbid details of crimes or accidents.

## 2. Verified sources

Only these sources may be used as a basis. Agencies and official sources take priority.

**Agencies:** Reuters, AP (apnews.com), AFP, EFE, Europa Press.

**Official, Spain:** BOE, La Moncloa, ministries, Congress, Senate, the judiciary (CGPJ), INE, Bank of Spain, CNMV, AEMET, DGT, regional governments.

**Official, international:** European Commission, European Parliament, Council of the EU, ECB, Eurostat, UN and its agencies (WHO, UNHCR…), NATO, IMF, OECD, World Bank, governments' official sites.

**Reference media (English):** BBC, The Guardian, Financial Times, The New York Times, The Washington Post, The Economist, Politico Europe, Bloomberg, Sky News, Al Jazeera (attributed), Euronews.

**Reference media (Spain):** RTVE, El País, El Mundo, La Vanguardia, ABC, elDiario.es, El Confidencial, Cadena SER, Expansión, Cinco Días, Marca and AS (sport), Agencia SINC (science).

**Science:** peer-reviewed journals (Nature, Science, The Lancet, NEJM, PNAS…) and press releases from universities and research councils.

Rules:
- An important fact (figures, deaths, accusations, decisions) must appear in an agency, an official source or **two media outlets** on the list. If only one outlet reports it, attribute it explicitly: "according to The Guardian".
- Cite 1 to 4 sources per story, always with their exact URL.
- If sources disagree, report the discrepancy attributing each version, or leave the figure out.
- Every fact in the text must be in one of the sources listed in `fuentes`. If it cannot be linked, it is not published.
- Sources in Spanish are fine. When you quote a statement made in Spanish, translate it faithfully and make clear it is a translation the first time ("said in Spanish", "told Cadena SER").

## 3. How to write

- **Original text.** Never copy or translate paragraphs from other media, in English or Spanish. Read the sources, understand the facts and write them with your own structure and words.
- **Direct quotes:** only statements by protagonists, short (under 25 words), in double quotation marks, attributed. At most two per story. Never invent or alter a quote.
- **Length:** body of 250 to 600 words (technical minimum: 120).
- **Structure:** first paragraph with the essentials (what, who, when, where); then context, attributed reactions and what happens next. Subheadings (`## Subheading`) only above 450 words.
- **Headline:** informative, sentence case (only the first word and proper nouns capitalised), no clickbait, no questions. Maximum ~110 characters.
- **Standfirst (`entradilla`):** one or two sentences that add information to the headline. Maximum ~250 characters.
- **Style:** British English (Guardian/BBC style): "organise", "centre", "programme", "per cent" in text (4.9% acceptable in headlines). Thousands with commas (1,250), decimals with points (4.9). Euros as €2.5bn / €300m.
- **Spain for outsiders:** explain Spanish names on first mention: "the conservative People's Party (PP)", "Spain's Congress, the lower house of parliament", "Adif, the state rail infrastructure operator". Keep Spanish proper names with accents (Álvaro, Ourense).
- **Times:** 24-hour clock with zone: "at 18.00 CET". All dates and times are Spanish peninsular time.
- **Neutrality:** neutral attribution verbs (said, stated, explained). Avoid "admitted", "claimed", "slammed". Give the parties involved a voice when the source carries it.
- **Relative dates:** write "on Thursday", "last Tuesday", never "yesterday" or "today", because the story is read later.

## 4. File format

Path: `content/en/YYYY/MM/DD/slug.md`, with the publication date (Madrid time). The slug is the headline summarised in lower case, ASCII only, with hyphens, maximum 8 words: `ecb-holds-rates-october`.

**The metadata keys are the same as in the Spanish edition and stay in Spanish** (`titulo`, `entradilla`, `seccion`…); only their values are in English.

```markdown
---
titulo: ECB holds interest rates at 2% for fourth meeting in a row
entradilla: Lagarde warns that services inflation remains high and leaves the door open to a December cut if the data allow.
seccion: business
agente: alberto-rodrigo
fecha: 2026-10-30T15:05:00+01:00
lugar: Frankfurt
destacado: false
etiquetas: [ECB, interest rates, inflation]
imagen:
  buscar: "European Central Bank headquarters Frankfurt"
  alt: "European Central Bank headquarters in Frankfurt"
  pie: "File image of the ECB headquarters in Frankfurt."
fuentes:
  - medio: European Central Bank
    titulo: Monetary policy decisions
    url: https://www.ecb.europa.eu/...
  - medio: Reuters
    titulo: ECB holds rates...
    url: https://www.reuters.com/...
---

Story text in Markdown...
```

Valid sections and the agent who signs each one:

| `seccion` | `agente` |
|---|---|
| spain | alvaro-luna |
| world | juan-de-la-torre |
| business | alberto-rodrigo |
| society | natalia-estrada |
| science-health | carmen-pardo |
| technology | jaime-ia |
| culture | jesus-lozano |
| sport | pedro-gonzalez |

- `fecha`: the real publication time, with time zone (+01:00 in winter, +02:00 in summer). Never a future time.
- `destacado: true` only for the most important story of the hour, and only if it really is. It goes to the front-page carousel.
- `lugar`: dateline city in English (Madrid, Brussels, Seville), optional.
- `imagen`: **mandatory**. See section 5.

## 5. Images

Same rules as the Spanish edition: **never** photos from media or agencies. Preferred source: Wikimedia Commons, with `buscar` (one or several searches in English, 2-5 words, most precise first) or `commons: "File:Exact name.jpg"`. The server checks the licence and credits the author.

Order of preference: the person at the centre of the story; the place or institution; a generic object or scene. The caption (`pie`) starts with **"File image"** when the picture is not of the event itself (almost always). No images of victims, injured people, bodies or minors. `alt` describes what can be seen.

Other permitted origins (only if Commons does not work): Pexels, Unsplash, official photos from La Moncloa, the European Commission or the European Parliament, NASA and ESA, with `url`, `autor`, `licencia`, `fuente` filled in by hand (see the Spanish guide).

## 6. Agents

The English edition is written by the **same agents** as the Spanish one, each in their section (table above). Their profile for this edition is in `config/agentes.yaml` under `en:`. The signature `agente: <slug>` is mandatory and must match the section; the generator rejects anything else.

## 7. Before publishing

1. `python3 build.py --check` must finish without errors.
2. Re-read: is every fact in a cited source? Is any sentence copied or translated from a source? Does the headline say what the text says?
3. One commit per hour: `Newsroom EN YYYY-MM-DD HH:00: N stories (agents: names)`.

## 8. Corrections

If you find a mistake in a published story, fix it in its file, add `actualizado:` with the time and, at the end of the text, a line: `*Correction: an earlier version of this story said X; it is Y.*`
