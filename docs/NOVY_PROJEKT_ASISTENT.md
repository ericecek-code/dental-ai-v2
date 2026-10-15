# 📞 Návrh nového projektu: AI Recepná pre zubnú ambulanciu

**Problém dnes:** pacienti sa prihlasujú iba telefonicky → asistentka prerušuje prácu, večer a v noci preregistrácie padajú, pripomienky sa nerobia.
**Cieľ:** pacient sa prihlási 24/7 tým kanálom, ktorý má rád — Viber, WhatsApp, web alebo telefónom s príjemným hlasom — bez ľudskej obsluhy.

---

## 1. Kanály (zoradené podľa ceny a dosahu na Slovensku)

| Kanál | Dosah v SR | Náklady | Fáza |
|---|---|---|---|
| **Viber bot** | ~70 % populácie (najsilnejší msg kanál v SR) | bot zadarmo, správy ~0.001–0.01 € | **Fáza 1** |
| **Web rezervačný widget** | 100 % (link z Google profilu/webu) | 0 € (vlastný) | **Fáza 1** |
| **WhatsApp Business** | ~40–60 % | utility správy ~0.004 €, service konverzácie 0 € | Fáza 1–2 |
| **SMS pripomienky** | 100 % | ~0.03–0.05 €/SMS (Twilio/lokálne brány) | Fáza 2 |
| **Hlas (telefón)** | 100 %, wow efekt | číslo ~2 €/mes + hovor ~0.02–0.10 €/min | **Fáza 2** |

## 2. Ako to funguje (architektúra)

```
Pacient: Viber/WhatsApp/web/telefón
   │
   ▼
Rezervačný agent (LLM + function calling)
   ├── kalendár ambulancie (voľné termíny podľa typu výkonu a dĺžky)
   ├── zápis rezervácie + meno + telefón
   ├── automatická pripomienka 24 h pred (správa/SMS)
   └── presmerovanie na človeka pri komplikácii (bolesť → "zavoláme do 15 min")
   │
   ▼
Asistentka: notifikácia + prehľad rezervácií (web panel)
```

**Hlasový reťaz (Fáza 2), všetko s free komponentmi:**
- Telefónne číslo: Twilio (~2 €/mes) alebo slovenský VoIP operátor
- Hlasový most: **Vapi** (najrýchlejší štart, free kredity na demo) alebo self-host **pipecat** (0 € za platformu)
- STT: **Whisper** (free, slovenčina OK)
- Mozog: LLM s function callingom (Gemini Flash free tier / lokálny model)
- **Hlas (TTS):** **Piper TTS — free, lokálny, rýchly aj na malom GPU; slovenské komunitné modely + kvalitná čeština.** ElevenLabs free tier (10 000 znakov/mes) ako prémiový fallback. Edge-TTS má len češtinu → nie.

## 3. Náklady mesačne (odhad)

| Varianta | Náklady |
|---|---|
| Komerčné (Arini, Kickcall a pod.) | 200–500 $/mes |
| **Naša Fáza 1 (Viber + web)** | **0–5 €/mes** |
| **Naša Fáza 2 (+ hlas, ~200 hovorov/mes)** | **10–25 €/mes** |

## 4. Plán realizácie

**Víkend 1 — Fáza 1 (písanie, bez hlasu):**
1. Kalendár (Supabase tabuľky: pracovné hodiny, typy výkonov + trvanie, rezervácie)
2. Web widget (React — rovnaký štýl ako Dental AI) + verejný link
3. Viber bot webhook (FastAPI — rovnaký backend vzor) s prirodzeným dialógom (LLM function calling na kalendár)
4. Panel pre asistentku: dnešné/zajtrajšie rezervácie, zrušenia

**Víkend 2 — Fáza 2 (hlas):**
5. Twilio číslo → Vapi agent (alebo pipecat self-host) s rovnakým kalendárovým nástrojom
6. Piper SK hlas + Whisper STT; testovacie hovory
7. Pripomienky: cron 24 h pred termínom (Viber/SMS)

## 5. Synergia s Dental AI

- Spoločná infraštruktúra (Supabase, rovnaký backend štýl, rovnaký login systém — kód z auth.py sa použije 1:1)
- Spoločný príbeh pre zubara: **„AI v ambulancii od A do Z"** — recepná prijíma pacienta 24/7, Dental AI pomáha lekárovi s RTG. To je už produkt, nie demo.
- Ochrana súkromia: rezervácia eviduje len meno + telefón, žiadne zdravotné dáta v chate.

## 6. Riziká

- GDPR: súhlas so spracovaním pri rezervácii (checkbox + zásady), dáta v EU regióne Supabase
- Lekárske triážovanie: bot NESMIE radíť — pri bolesti/úrazoch vždy ľudské presmerovanie
- Viber/WhatsApp API schválenie účtu obchodníka: 1–2 týždne (začať čoskoro)
- Hlasová agentka musí vedieť povedať „to neviem posúdiť, spojíme vás s lekárskou sestrou" — guardrails v promte
