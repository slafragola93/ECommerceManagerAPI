# Esempio Calcoli FatturaPA Corretti

## Scenario
Ordine con 2 prodotti:
- Prodotto A: €100 + IVA 22% = €122
- Prodotto B: €50 + IVA 22% = €61
- Totale ordine: €183

**Nota**: L'`ImportoTotaleDocumento` viene calcolato come somma di tutte le linee di dettaglio (imponibile + imposta)

## Calcoli Corretti

### Per ogni linea di dettaglio:

#### Prodotto A (€100 + IVA 22%)
- **Prezzo con IVA**: €100.00
- **Prezzo unitario netto**: €100.00 ÷ 1.22 = €81.97
- **Imposta per unità**: €100.00 - €81.97 = €18.03
- **Quantità**: 1
- **Prezzo totale netto**: €81.97 × 1 = €81.97
- **Imposta totale**: €18.03 × 1 = €18.03

#### Prodotto B (€50 + IVA 22%)
- **Prezzo con IVA**: €50.00
- **Prezzo unitario netto**: €50.00 ÷ 1.22 = €40.98
- **Imposta per unità**: €50.00 - €40.98 = €9.02
- **Quantità**: 1
- **Prezzo totale netto**: €40.98 × 1 = €40.98
- **Imposta totale**: €9.02 × 1 = €9.02

### Riepilogo IVA
- **Totale Imponibile**: €81.97 + €40.98 = €122.95
- **Totale Imposta**: €18.03 + €9.02 = €27.05
- **Totale con IVA**: €122.95 + €27.05 = €150.00

### ImportoTotaleDocumento
- **ImportoTotaleDocumento**: €150.00 (totale con IVA calcolato dalle linee)

## XML Generato

```xml
<DettaglioLinee>
  <NumeroLinea>1</NumeroLinea>
  <Descrizione>Prodotto A</Descrizione>
  <Quantita>1.00</Quantita>
  <PrezzoUnitario>81.97</PrezzoUnitario>
  <PrezzoTotale>81.97</PrezzoTotale>
  <AliquotaIVA>22.00</AliquotaIVA>
</DettaglioLinee>

<DettaglioLinee>
  <NumeroLinea>2</NumeroLinea>
  <Descrizione>Prodotto B</Descrizione>
  <Quantita>1.00</Quantita>
  <PrezzoUnitario>40.98</PrezzoUnitario>
  <PrezzoTotale>40.98</PrezzoTotale>
  <AliquotaIVA>22.00</AliquotaIVA>
</DettaglioLinee>

<DatiRiepilogo>
  <AliquotaIVA>22.00</AliquotaIVA>
  <ImponibileImporto>122.95</ImponibileImporto>
  <Imposta>27.05</Imposta>
  <EsigibilitaIVA>I</EsigibilitaIVA>
</DatiRiepilogo>

<DatiPagamento>
  <CondizioniPagamento>TP02</CondizioniPagamento>
  <DettaglioPagamento>
    <ModalitaPagamento>MP05</ModalitaPagamento>
    <ImportoPagamento>150.00</ImportoPagamento>
  </DettaglioPagamento>
</DatiPagamento>
```

## Correzioni Implementate

1. **Provincia**: Limitata a 2 caratteri (NA, MI, etc.)
2. **ImportoTotaleDocumento**: Calcolato come somma di tutte le linee (imponibile + imposta)
3. **PrezzoUnitario**: Calcolato come prezzo con IVA ÷ 1.22
4. **PrezzoTotale**: Prezzo unitario netto × quantità
5. **ImponibileImporto**: Somma di tutti i prezzi netti
6. **Imposta**: Somma di tutte le imposte per linea
7. **ImportoPagamento**: Usa il totale con IVA calcolato dalle linee
