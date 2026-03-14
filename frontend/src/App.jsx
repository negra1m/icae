import { useState, useEffect, useCallback, useRef } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell, ReferenceLine,
} from "recharts";

const API = import.meta.env.VITE_API_URL || (
  window.location.port === "3000" && window.location.hostname === "localhost"
    ? "http://localhost:8000" : "/api"
);

const C = {
  bg:"#0a0e1a", surface:"#111827", card:"#141e2e", border:"#1e2d42",
  accent:"#00e5a0", accentDim:"#00e5a020", warn:"#ff6b35", warnDim:"#ff6b3520",
  muted:"#4a6080", text:"#e2eaf4", textDim:"#7a94b0",
};

const BIOMA_COR = {
  "Amazônia":"#2d6a4f","Amazônia Legal":"#1b4332","Cerrado":"#d4a017",
  "Caatinga":"#c77d35","Mata Atlântica":"#40916c","Pampa":"#74c69d","Pantanal":"#1e6091",
};

// Formata valor em R$ ou US$ de forma inteligente (K / M / B)
function fmtBRL(v, prefix="R$") {
  if (!v || isNaN(v)) return `${prefix}0`;
  if (v >= 1e9)  return `${prefix}${(v/1e9).toFixed(1)}B`;
  if (v >= 1e6)  return `${prefix}${(v/1e6).toFixed(0)}M`;
  if (v >= 1e3)  return `${prefix}${(v/1e3).toFixed(0)}k`;
  return `${prefix}${v.toFixed(0)}`;
}
function fmtUSD(v) { return fmtBRL(v, "US$"); }

// ── i18n ─────────────────────────────────────────────────────────────────────
const LANG = {
  pt: {
    // header
    appSubtitle: "ÍNDICE DE COERÊNCIA AMBIENTAL ECONÔMICA · NACIONAL",
    allStates:   "Todos os estados",
    allBiomes:   "Todos os biomas",
    updating:    "ATUALIZANDO...",
    offline:     "OFFLINE",
    langToggle:  "EN",

    // tabs
    tabMap:      "🗺️ Mapa",
    tabOverview: "📊 Resumo",
    tabRanking:  "🏆 Ranking",
    tabScatter:  "🔍 Crédito × Risco",
    tabPrivate:  "🏦 Incentivos Privados",
    tabBiomes:   "🌿 Biomas",
    tabSim:      "⚙️ Simulador",
    tabHow:      "❓ Como funciona",

    // map tab
    mapTitle:    "Mapa do Desmatamento no Brasil",
    mapDesc:     "Estados coloridos pela intensidade do desmatamento registrado pelo PRODES/INPE. Passe o mouse para ver detalhes. Use scroll ou os botões para navegar.",
    mapLoading:  "Carregando mapa do Brasil...",
    mapNoConn:   "Mapa indisponível (sem conexão com IBGE)",
    mapCardTitle:"Mapa do Desmatamento",
    mapCardSub:  "por estado — PRODES/INPE",
    legendTitle: "DESMATAMENTO",
    legendCrit:  "Crítico",
    legendHigh:  "Alto",
    legendMod:   "Moderado",
    legendNone:  "Sem dados",
    listDeforest:"🔴 Mais Desmatamento",
    listCredit:  "💰 Maior Crédito + Alto Risco",

    // tooltip
    ttDeforest:  "Desmatamento",
    ttCredit:    "Crédito",
    ttRisk:      "Risco",

    // overview
    overviewTitle:"Visão Geral Nacional",
    overviewDesc: "Cruzamento de crédito rural (SICOR/BCB) com desmatamento (PRODES/INPE) em todos os 6 biomas do Brasil.",
    realData:    " ✅ Dados reais carregados.",
    demoData:    " ⚠️ Exibindo dados demo — aguarde sincronização.",
    kpiMun:      "Municípios analisados",
    kpiMunSub:   "com crédito rural + desmatamento registrado",
    kpiMunTip:   "Total de municípios que receberam crédito rural e têm dados de desmatamento PRODES disponíveis.",
    kpiScore:    "Nota média",
    kpiResp:     "Uso responsável",
    kpiRespSub:  "ICAE ≥ 70 · sem infrações graves",
    kpiCrit:     "Casos críticos",
    kpiCritSub:  "ICAE < 40 · risco ambiental alto",
    kpiCritTip:  "Municípios que receberam crédito público significativo e apresentam alto desmatamento ou infrações graves.",
    chartScores: "Distribuição das notas",
    chartScoresSub: "frequência por faixa de pontuação (0–100)",
    chartBiomes: "Por bioma",
    chartBiomesSub: "ICAE médio e área desmatada por bioma",
    chartRegions: "Por região do Brasil",
    chartRegionsSub: "nota média de coerência ambiental por grande região",
    munLabel:    "mun.",

    // ranking
    rankTitle:   "Ranking de Coerência",
    rankSearch:  "🔍 Buscar município, estado ou bioma...",
    rankMuns:    "municípios",
    prodLabel:   "Produtor",
    colRank:     "#",
    colMun:      "Município / Estado",
    colUF:       "UF",
    colBiome:    "Bioma",
    colScore:    "Nota",
    colBar:      "Barra",
    colRisk:     "Risco",
    colStatus:   "Situação",
    riskHigh:    "🔴 Alto",
    riskMed:     "🟡 Médio",
    riskLow:     "🟢 Baixo",

    // scatter
    scatterTitle: "Crédito Público × Risco Ambiental",
    scatterDesc:  "Ideal = canto inferior direito (muito crédito, pouco desmatamento). Pior = canto superior direito. Tamanho da bolha = volume de crédito recebido.",
    axisCredit:   "Crédito público →",
    axisRisk:     "↑ Risco ambiental",

    // private incentives
    privTitle:   "Incentivos Privados por Município",
    privDesc:    "Cruza dois fluxos de dinheiro privado com o desmatamento: desembolsos do BNDES (agronegócio) e exportações de commodities via Comex Stat/MDIC. Junto com o crédito rural do SICOR, formam o quadro completo do incentivo financeiro por trás do desmatamento.",
    privBNDESDesc:"Desembolsos agronegócio — CSV público (dadosabertos.bndes.gov.br)",
    privComexDesc:"Exportações soja, boi, madeira etc — API pública MDIC",
    privSICORDesc:"Crédito rural Pronaf/ABC — já no ICAE principal",
    privLoading: "Carregando dados privados...",
    privLoadSub: "BNDES (~70MB) e Comex Stat estão sendo baixados em background.",
    privForce:   "Forçar atualização",
    privUpdating:"Atualizando...",
    kpiPrivMun:  "Municípios com dados privados",
    kpiBNDES:    "BNDES agro total",
    kpiComex:    "Exportações agro total",
    kpiPrivTotal:"Fluxo privado total",
    topBNDES:    "🏦 Top BNDES Agronegócio",
    topBNDESSub: "municípios com maiores desembolsos BNDES em agro/florestal",
    topComex:    "📦 Top Exportações Agro",
    topComexSub: "municípios com maior valor exportado de commodities agrícolas",
    critTitle:   "🚨 Casos mais críticos — Fluxo financeiro total × Desmatamento",
    critDesc:    "Municípios que concentram o maior volume de incentivos públicos + privados E alto desmatamento. Ordenado por: (crédito rural + BNDES + exportações) × risco ambiental.",
    colPubCredit:"Crédito Público",
    colBNDES:    "BNDES Agro",
    colExports:  "Exportações",
    colDeforest: "Desmatamento",
    critNote:    "⚠️ Importante: exportações representam receita, não necessariamente incentivo direto — mas indicam o retorno financeiro que torna economicamente racional o desmatamento.",

    // biomes
    biomesTitle: "Análise por Bioma",
    biomesSub:   "PRODES/INPE cobre todos os 6 biomas brasileiros desde 2022.",
    kpiAvgScore: "NOTA MÉDIA",
    kpiMunCount: "MUNICÍPIOS",
    kpiDeforest: "DESMAT. TOTAL",
    kpiCreditTot:"CRÉDITO TOTAL",

    // simulator
    simTitle:    "Simulador de Pesos",
    simDesc:     "Ajuste os pesos de cada componente e recalcule o ranking conforme seus critérios de análise.",
    simDeforest: "α1 · Desmatamento",
    simDeforestD:"Peso do desmatamento incremental (delta km²) no cálculo do risco",
    simFines:    "α2 · Multas ambientais",
    simFinesD:   "Peso das autuações e multas do IBAMA (proxy: delta × R$1k/km²)",
    simRecid:    "α3 · Reincidência",
    simRecidD:   "Peso da repetição de infrações em anos anteriores",
    simEmbargo:  "α4 · Embargo",
    simEmbargoD: "Peso do município ter propriedades embargadas ativas",
    simTotal:    "Total",
    simWarning:  "⚠️ Precisa somar exatamente 100%",
    simBtn:      "Recalcular ranking →",
    simCalc:     "Calculando...",
    simAvg:      "Nota média simulada",
    simRankTitle:"Ranking com seus critérios",
    simRankDef:  "Ranking padrão",
    simTop20:    "— Top 20",

    // how it works
    howTitle:    "Como funciona o ICAE?",
    howDesc:     "O ICAE cruza duas perguntas simples: quem recebeu dinheiro público para o campo? E esse dinheiro veio junto com desmatamento? Quanto mais dinheiro e mais desmatamento, pior a nota.",
    howQ1:       "De onde vêm os dados de crédito?",
    howA1:       "Do SICOR, sistema do Banco Central do Brasil. Cada contrato de crédito rural — do Pronaf ao Pronamp ao ABC — é registrado por município. São dados públicos, atualizados anualmente, cobrindo todos os 5.570 municípios do país.",
    howQ2:       "De onde vêm os dados de desmatamento?",
    howA2:       "Do PRODES, programa de monitoramento por satélite do INPE. Desde 2022 cobre todos os 6 biomas brasileiros: Amazônia, Cerrado, Mata Atlântica, Caatinga, Pampa e Pantanal. Os dados são anuais e disponíveis via TerraBrasilis.",
    howQ3:       "Como os dados são cruzados?",
    howA3:       "Por código IBGE do município. Quando o SICOR informa o código IBGE na operação, o merge é exato. Quando só há nome, usa-se normalização textual (remove acentos, maiúsculas). Municípios sem correspondência em ambas as bases são excluídos.",
    howQ4:       "O que ainda falta para ser 100% real?",
    howA4:       "Multas e embargos individuais por propriedade dependem da API do IBAMA, que ainda não está disponível de forma pública e estruturada. Atualmente essas variáveis são estimadas via proxy (delta de desmatamento × R$1.000/km²). Assim que a integração IBAMA/SINAFLOR for possível, o índice ficará ainda mais preciso.",
    formulaTitle:"A fórmula",
    step1n:      "Passo 1", step1eq:"X_norm = (X − min) / (max − min)", step1d:"Coloca todas as variáveis na mesma escala (0 a 1)",
    step2n:      "Passo 2", step2eq:"Risk = α1·Desmate + α2·Multas + α3·Reincidência + α4·Embargo", step2d:"Combina os 4 fatores de risco num único número",
    step3n:      "Passo 3", step3eq:"ICAE = (1 − Risco) × (1 − Crédito)", step3d:"Penaliza quem tem muito crédito E muito risco ao mesmo tempo",
    openSrc:     "Código aberto · Auditável · Reproduzível.",
    openSrcSub:  "Todas as fontes são públicas. Todo peso é configurável. Nenhum cálculo é oculto.",
    openSrcTag:  "Licença AGPL-3.0 · ",
    openSrcSlogan: "Transparência não é discurso — é arquitetura.",

    // icae labels
    labelGood:   "✅ Boa coerência",
    labelWarn:   "⚠️ Atenção",
    labelBad:    "🚨 Problema grave",
    labelDeforestUnit: "km²",
  },
  en: {
    appSubtitle: "ENVIRONMENTAL-ECONOMIC COHERENCE INDEX · NATIONAL",
    allStates:   "All states",
    allBiomes:   "All biomes",
    updating:    "UPDATING...",
    offline:     "OFFLINE",
    langToggle:  "PT",

    tabMap:      "🗺️ Map",
    tabOverview: "📊 Overview",
    tabRanking:  "🏆 Ranking",
    tabScatter:  "🔍 Credit × Risk",
    tabPrivate:  "🏦 Private Incentives",
    tabBiomes:   "🌿 Biomes",
    tabSim:      "⚙️ Simulator",
    tabHow:      "❓ How it works",

    mapTitle:    "Deforestation Map of Brazil",
    mapDesc:     "States colored by deforestation intensity from PRODES/INPE. Hover to see details. Scroll or use buttons to navigate.",
    mapLoading:  "Loading Brazil map...",
    mapNoConn:   "Map unavailable (no IBGE connection)",
    mapCardTitle:"Deforestation Map",
    mapCardSub:  "by state — PRODES/INPE",
    legendTitle: "DEFORESTATION",
    legendCrit:  "Critical",
    legendHigh:  "High",
    legendMod:   "Moderate",
    legendNone:  "No data",
    listDeforest:"🔴 Most Deforestation",
    listCredit:  "💰 Highest Credit + High Risk",

    ttDeforest:  "Deforestation",
    ttCredit:    "Credit",
    ttRisk:      "Risk",

    overviewTitle:"National Overview",
    overviewDesc: "Cross-reference of rural credit (SICOR/BCB) with deforestation (PRODES/INPE) across all 6 Brazilian biomes.",
    realData:    " ✅ Live data loaded.",
    demoData:    " ⚠️ Showing demo data — awaiting sync.",
    kpiMun:      "Municipalities analysed",
    kpiMunSub:   "with rural credit + deforestation data",
    kpiMunTip:   "Total municipalities that received rural credit and have PRODES deforestation data available.",
    kpiScore:    "Average score",
    kpiResp:     "Responsible use",
    kpiRespSub:  "ICAE ≥ 70 · no serious violations",
    kpiCrit:     "Critical cases",
    kpiCritSub:  "ICAE < 40 · high environmental risk",
    kpiCritTip:  "Municipalities that received significant public credit and show high deforestation or serious violations.",
    chartScores: "Score distribution",
    chartScoresSub: "frequency by score range (0–100)",
    chartBiomes: "By biome",
    chartBiomesSub: "Average ICAE and deforested area per biome",
    chartRegions: "By Brazilian region",
    chartRegionsSub: "Average environmental coherence score by major region",
    munLabel:    "mun.",

    rankTitle:   "Coherence Ranking",
    rankSearch:  "🔍 Search municipality, state or biome...",
    rankMuns:    "municipalities",
    prodLabel:   "Producer",
    colRank:     "#",
    colMun:      "Municipality / State",
    colUF:       "State",
    colBiome:    "Biome",
    colScore:    "Score",
    colBar:      "Bar",
    colRisk:     "Risk",
    colStatus:   "Status",
    riskHigh:    "🔴 High",
    riskMed:     "🟡 Medium",
    riskLow:     "🟢 Low",

    scatterTitle: "Public Credit × Environmental Risk",
    scatterDesc:  "Ideal = bottom-right (lots of credit, little deforestation). Worst = top-right. Bubble size = credit volume received.",
    axisCredit:   "Public credit →",
    axisRisk:     "↑ Environmental risk",

    privTitle:   "Private Incentives by Municipality",
    privDesc:    "Cross-references two private money flows with deforestation: BNDES disbursements (agribusiness) and commodity exports via Comex Stat/MDIC. Together with SICOR rural credit, they form the complete picture of financial incentives driving deforestation.",
    privBNDESDesc:"Agribusiness disbursements — public CSV (dadosabertos.bndes.gov.br)",
    privComexDesc:"Soy, beef, timber exports etc — MDIC public API",
    privSICORDesc:"Rural credit Pronaf/ABC — already in main ICAE",
    privLoading: "Loading private data...",
    privLoadSub: "BNDES (~70MB) and Comex Stat are being downloaded in background.",
    privForce:   "Force refresh",
    privUpdating:"Updating...",
    kpiPrivMun:  "Municipalities with private data",
    kpiBNDES:    "BNDES agro total",
    kpiComex:    "Agro exports total",
    kpiPrivTotal:"Total private flow",
    topBNDES:    "🏦 Top BNDES Agribusiness",
    topBNDESSub: "municipalities with highest BNDES agro/forestry disbursements",
    topComex:    "📦 Top Agro Exports",
    topComexSub: "municipalities with highest agricultural commodity export value",
    critTitle:   "🚨 Most critical cases — Total financial flow × Deforestation",
    critDesc:    "Municipalities concentrating the highest volume of public + private incentives AND high deforestation. Sorted by: (rural credit + BNDES + exports) × environmental risk.",
    colPubCredit:"Public Credit",
    colBNDES:    "BNDES Agro",
    colExports:  "Exports",
    colDeforest: "Deforestation",
    critNote:    "⚠️ Note: exports represent revenue, not necessarily a direct incentive — but they indicate the financial return that makes deforestation economically rational.",

    biomesTitle: "Biome Analysis",
    biomesSub:   "PRODES/INPE covers all 6 Brazilian biomes since 2022.",
    kpiAvgScore: "AVG SCORE",
    kpiMunCount: "MUNICIPALITIES",
    kpiDeforest: "TOTAL DEFOREST.",
    kpiCreditTot:"TOTAL CREDIT",

    simTitle:    "Weight Simulator",
    simDesc:     "Adjust the weight of each component and recalculate the ranking according to your analysis criteria.",
    simDeforest: "α1 · Deforestation",
    simDeforestD:"Weight of incremental deforestation (delta km²) in risk calculation",
    simFines:    "α2 · Environmental fines",
    simFinesD:   "Weight of IBAMA fines and sanctions (proxy: delta × R$1k/km²)",
    simRecid:    "α3 · Recidivism",
    simRecidD:   "Weight of repeated violations in prior years",
    simEmbargo:  "α4 · Embargo",
    simEmbargoD: "Weight of municipality having active embargoed properties",
    simTotal:    "Total",
    simWarning:  "⚠️ Must add up to exactly 100%",
    simBtn:      "Recalculate ranking →",
    simCalc:     "Calculating...",
    simAvg:      "Simulated average score",
    simRankTitle:"Ranking with your criteria",
    simRankDef:  "Default ranking",
    simTop20:    "— Top 20",

    howTitle:    "How does ICAE work?",
    howDesc:     "ICAE crosses two simple questions: who received public money for agriculture? And did that money come with deforestation? The more money and the more deforestation, the worse the score.",
    howQ1:       "Where does the credit data come from?",
    howA1:       "From SICOR, the Central Bank of Brazil's system. Each rural credit contract — from Pronaf to Pronamp to ABC — is registered by municipality. Public data, updated annually, covering all 5,570 Brazilian municipalities.",
    howQ2:       "Where does the deforestation data come from?",
    howA2:       "From PRODES, INPE's satellite monitoring program. Since 2022 it covers all 6 Brazilian biomes: Amazon, Cerrado, Atlantic Forest, Caatinga, Pampa and Pantanal. Annual data available via TerraBrasilis.",
    howQ3:       "How is the data cross-referenced?",
    howA3:       "By the municipality's IBGE code. When SICOR provides the IBGE code in the operation, the merge is exact. When only a name is available, text normalisation is used (removes accents, uppercase). Municipalities without a match in both databases are excluded.",
    howQ4:       "What's still missing for 100% real data?",
    howA4:       "Individual property fines and embargos depend on the IBAMA API, which is not yet publicly available in structured form. These variables are currently estimated via proxy (deforestation delta × R$1,000/km²). Once IBAMA/SINAFLOR integration is possible, the index will be even more precise.",
    formulaTitle:"The formula",
    step1n:      "Step 1", step1eq:"X_norm = (X − min) / (max − min)", step1d:"Puts all variables on the same scale (0 to 1)",
    step2n:      "Step 2", step2eq:"Risk = α1·Deforest + α2·Fines + α3·Recidivism + α4·Embargo", step2d:"Combines the 4 risk factors into a single number",
    step3n:      "Step 3", step3eq:"ICAE = (1 − Risk) × (1 − Credit)", step3d:"Penalises those with high credit AND high risk simultaneously",
    openSrc:     "Open source · Auditable · Reproducible.",
    openSrcSub:  "All sources are public. Every weight is configurable. No calculation is hidden.",
    openSrcTag:  "License AGPL-3.0 · ",
    openSrcSlogan: "Transparency is not rhetoric — it's architecture.",

    labelGood:   "✅ Good coherence",
    labelWarn:   "⚠️ Attention",
    labelBad:    "🚨 Serious problem",
    labelDeforestUnit: "km²",
  },
};


function icaeColor(v) {
  if (v >= 0.7) return "#00e5a0";
  if (v >= 0.4) return "#f9c74f";
  return "#ff6b35";
}
// Passamos T (dicionário da língua ativa) como argumento para as funções de label
function icaeLabel(v, T) {
  if (!T) T = LANG.pt;
  if (v >= 0.7) return T.labelGood;
  if (v >= 0.4) return T.labelWarn;
  return T.labelBad;
}
function desmatLabel(v, T) {
  if (!T) T = LANG.pt;
  if (v === "crítico")  return "🔴 " + T.legendCrit;
  if (v === "alto")     return "🟠 " + T.legendHigh;
  if (v === "moderado") return "🟡 " + T.legendMod;
  return "🟢 Estável";
}

function ScoreBar({ value }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div style={{ width:"100%", height:6, background:"#1e2d42", borderRadius:3, overflow:"hidden" }}>
      <div style={{ width:`${pct}%`, height:"100%", background:`linear-gradient(90deg,${icaeColor(value)},${icaeColor(value)}cc)`, borderRadius:3, transition:"width 0.6s ease" }} />
    </div>
  );
}

function KpiCard({ label, value, sub, accent, tooltip }) {
  const [h, setH] = useState(false);
  return (
    <div onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
      style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:"20px 24px", flex:1, borderTop:`2px solid ${accent||C.accent}`, position:"relative", cursor: tooltip?"help":"default" }}>
      <div style={{ color:C.textDim, fontSize:11, textTransform:"uppercase", letterSpacing:"0.1em", fontFamily:"DM Mono,monospace" }}>{label}</div>
      <div style={{ color:C.text, fontSize:30, fontFamily:"Syne,sans-serif", fontWeight:800, marginTop:4 }}>{value}</div>
      {sub && <div style={{ color:C.textDim, fontSize:12, marginTop:4 }}>{sub}</div>}
      {tooltip && h && (
        <div style={{ position:"absolute", bottom:"calc(100% + 8px)", left:0, right:0, background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:"10px 14px", fontSize:12, color:C.text, zIndex:10, boxShadow:"0 4px 24px #0006" }}>{tooltip}</div>
      )}
    </div>
  );
}

const CustomTooltip = ({ active, payload, T: TT }) => {
  const T2 = TT || LANG.pt;
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:"10px 14px", fontSize:12, fontFamily:"DM Mono,monospace", color:C.text }}>
      <div style={{ color:C.accent, fontWeight:700 }}>{d.municipio || d.entity_id}</div>
      {d.uf && <div style={{ color:C.textDim }}>{d.uf} {d.bioma ? `· ${d.bioma}` : ""}</div>}
      {d.icae !== undefined && <div>ICAE: <span style={{ color:icaeColor(d.icae) }}>{(d.icae*100).toFixed(1)}/100 — {icaeLabel(d.icae, T2)}</span></div>}
      {d.risk !== undefined && <div>{T2.ttRisk}: <span style={{ color:C.warn }}>{(d.risk*100).toFixed(1)}%</span></div>}
      {d.delta_km2 !== undefined && <div>{T2.ttDeforest}: <span style={{ color:C.warn }}>+{d.delta_km2?.toFixed(0)} km²</span></div>}
      {d.credito_total !== undefined && <div>{T2.ttCredit}: {fmtBRL(d.credito_total)}</div>}
    </div>
  );
};

// ── Mapa do Brasil via SVG (IBGE GeoJSON → coordenadas projetadas) ──────────

function MapaBrasil({ dados, filtroUF, onMunicipioClick, T }) {
  const svgRef = useRef(null);
  const [geoData, setGeoData] = useState(null);
  const [tooltip, setTooltip] = useState(null);
  const [loading, setLoading] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState(null);

  useEffect(() => {
    // GeoJSON dos estados do Brasil via IBGE (malha estadual)
    fetch("https://servicodados.ibge.gov.br/api/v2/malhas/BR?resolucao=2&formato=application/vnd.geo+json")
      .then(r => r.json())
      .then(data => { setGeoData(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const dadosMap = {};
  dados.forEach(d => {
    const key = d.uf || d.municipio;
    if (!dadosMap[key] || d.delta_km2 > dadosMap[key].delta_km2) {
      dadosMap[key] = d;
    }
  });

  // Projeção simples: lat/lon → x,y no SVG (800×700)
  const W = 800, H = 700;
  const LON_MIN = -74, LON_MAX = -28, LAT_MIN = -34, LAT_MAX = 6;
  function project([lon, lat]) {
    const x = ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * W;
    const y = ((LAT_MAX - lat) / (LAT_MAX - LAT_MIN)) * H;
    return [x, y];
  }

  function pathFromGeo(geometry) {
    if (!geometry) return "";
    const coords = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
    return coords.map(polygon =>
      polygon.map(ring =>
        ring.map((pt, i) => {
          const [x, y] = project(pt);
          return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ") + " Z"
      ).join(" ")
    ).join(" ");
  }

  function getUFfromFeature(f) {
    return f.properties?.codarea?.toString().substring(0, 2);
  }

  // Calcula cor do estado baseado no desmatamento
  function stateColor(coduf) {
    const UF_MAP = {"11":"RO","12":"AC","13":"AM","14":"RR","15":"PA","16":"AP","17":"TO","21":"MA","22":"PI","23":"CE","24":"RN","25":"PB","26":"PE","27":"AL","28":"SE","29":"BA","31":"MG","32":"ES","33":"RJ","35":"SP","41":"PR","42":"SC","43":"RS","50":"MS","51":"MT","52":"GO","53":"DF"};
    const uf = UF_MAP[coduf];
    if (!uf || !dadosMap[uf]) return "#1a2535";
    const d = dadosMap[uf];
    if (d.severidade === "crítico")  return "#ff2a00cc";
    if (d.severidade === "alto")     return "#ff6b35cc";
    if (d.severidade === "moderado") return "#f9c74fcc";
    if (d.icae !== undefined) return icaeColor(d.icae) + "aa";
    return "#2a3a50";
  }

  const handleMouseMove = (e) => {
    if (dragging && dragStart) {
      setPan(p => ({ x: p.x + e.clientX - dragStart.x, y: p.y + e.clientY - dragStart.y }));
      setDragStart({ x: e.clientX, y: e.clientY });
    }
  };

  const maxDesmat = Math.max(...dados.map(d => d.delta_km2 || 0), 1);

  return (
    <div style={{ position:"relative", width:"100%", height:520, background:C.card, borderRadius:12, border:`1px solid ${C.border}`, overflow:"hidden", userSelect:"none" }}>
      {loading && (
        <div style={{ position:"absolute", inset:0, display:"flex", alignItems:"center", justifyContent:"center", color:C.textDim, fontFamily:"DM Mono", fontSize:13 }}>
          <span className="pulse">{T.mapLoading}</span>
        </div>
      )}

      {!loading && geoData && (
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} width="100%" height="100%"
          style={{ cursor: dragging ? "grabbing" : "grab" }}
          onMouseDown={e => { setDragging(true); setDragStart({ x:e.clientX, y:e.clientY }); }}
          onMouseMove={handleMouseMove}
          onMouseUp={() => { setDragging(false); setDragStart(null); }}
          onMouseLeave={() => { setDragging(false); setDragStart(null); }}>

          <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
            {geoData.features?.map((f, i) => {
              const coduf = f.properties?.codarea?.toString();
              const d = pathFromGeo(f.geometry);
              const cor = stateColor(coduf);
              const UF_MAP = {"11":"RO","12":"AC","13":"AM","14":"RR","15":"PA","16":"AP","17":"TO","21":"MA","22":"PI","23":"CE","24":"RN","25":"PB","26":"PE","27":"AL","28":"SE","29":"BA","31":"MG","32":"ES","33":"RJ","35":"SP","41":"PR","42":"SC","43":"RS","50":"MS","51":"MT","52":"GO","53":"DF"};
              const uf = UF_MAP[coduf] || coduf;
              const info = dadosMap[uf];
              return (
                <path key={i} d={d}
                  fill={cor}
                  stroke={C.border}
                  strokeWidth={0.5}
                  style={{ cursor: info ? "pointer" : "default", transition:"fill 0.3s" }}
                  onMouseEnter={e => {
                    if (info) setTooltip({ x: e.clientX, y: e.clientY, data: info, uf });
                  }}
                  onMouseLeave={() => setTooltip(null)}
                  onClick={() => info && onMunicipioClick && onMunicipioClick(uf)}
                />
              );
            })}
          </g>
        </svg>
      )}

      {!loading && !geoData && (
        <div style={{ position:"absolute", inset:0, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", color:C.textDim, gap:8 }}>
          <span style={{ fontSize:24 }}>🗺️</span>
          <span style={{ fontSize:13, fontFamily:"DM Mono" }}>{T.mapNoConn}</span>
        </div>
      )}

      {/* Controles zoom */}
      <div style={{ position:"absolute", bottom:16, right:16, display:"flex", flexDirection:"column", gap:4 }}>
        {[{l:"+",fn:() => setZoom(z => Math.min(z*1.3,8))},{l:"−",fn:() => setZoom(z => Math.max(z/1.3,1))},{l:"⊙",fn:() => { setZoom(1); setPan({x:0,y:0}); }}].map(b => (
          <button key={b.l} onClick={b.fn} style={{ width:32, height:32, background:C.surface, border:`1px solid ${C.border}`, borderRadius:6, color:C.text, cursor:"pointer", fontSize:14 }}>{b.l}</button>
        ))}
      </div>

      {/* Legenda */}
      <div style={{ position:"absolute", bottom:16, left:16, background:`${C.bg}cc`, border:`1px solid ${C.border}`, borderRadius:8, padding:"8px 12px", fontSize:11, fontFamily:"DM Mono" }}>
        <div style={{ color:C.textDim, marginBottom:6, textTransform:"uppercase", letterSpacing:"0.08em" }}>{T.legendTitle}</div>
        {[["#ff2a00",T.legendCrit],["#ff6b35",T.legendHigh],["#f9c74f",T.legendMod],["#1a2535",T.legendNone]].map(([cor,l]) => (
          <div key={l} style={{ display:"flex", alignItems:"center", gap:6, marginBottom:3 }}>
            <div style={{ width:12, height:12, background:cor, borderRadius:2 }} />
            <span style={{ color:C.textDim }}>{l}</span>
          </div>
        ))}
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div style={{
          position:"fixed", left:tooltip.x+12, top:tooltip.y-40,
          background:C.surface, border:`1px solid ${C.border}`,
          borderRadius:8, padding:"10px 14px", fontSize:12,
          fontFamily:"DM Mono", color:C.text, zIndex:1000,
          boxShadow:"0 4px 20px #0008", pointerEvents:"none",
          transform:"translateY(-50%)",
        }}>
          <div style={{ color:C.accent, fontWeight:700, marginBottom:4 }}>{tooltip.uf} — {tooltip.data.municipio || tooltip.uf}</div>
          {tooltip.data.delta_km2 !== undefined && (
            <div>🌳 {T.ttDeforest}: <span style={{ color:C.warn }}>+{tooltip.data.delta_km2?.toFixed(0)} km²</span></div>
          )}
          {tooltip.data.icae !== undefined && (
            <div>📊 ICAE: <span style={{ color:icaeColor(tooltip.data.icae) }}>{(tooltip.data.icae*100).toFixed(0)}/100</span></div>
          )}
          {tooltip.data.credito_total !== undefined && (
            <div>💰 {T.ttCredit}: {fmtBRL(tooltip.data.credito_total)}</div>
          )}
          {tooltip.data.severidade && (
            <div style={{ marginTop:4, color: tooltip.data.severidade==="crítico" ? C.warn : C.textDim }}>
              {desmatLabel(tooltip.data.severidade)}
            </div>
          )}
        </div>
      )}

      {/* Titulo */}
      <div style={{ position:"absolute", top:16, left:16 }}>
        <div style={{ fontFamily:"Syne", fontWeight:800, fontSize:14, color:C.text }}>{T.mapCardTitle}</div>
        <div style={{ fontSize:10, color:C.textDim, fontFamily:"DM Mono" }}>{T.mapCardSub} {new Date().getFullYear()}</div>
      </div>
    </div>
  );
}

// ── APP PRINCIPAL ────────────────────────────────────────────

export default function App() {
  const [lang, setLang] = useState("pt");
  const T = LANG[lang];
  const [ranking, setRanking]   = useState([]);
  const [municipios, setMun]    = useState([]);
  const [mapaData, setMapaData] = useState([]);
  const [biomas, setBiomas]     = useState([]);
  const [regioes, setRegioes]   = useState([]);
  const [formula, setFormula]   = useState(null);
  const [status, setStatus]     = useState(null);
  const [privados, setPrivados] = useState([]);
  const [cruzado, setCruzado]   = useState([]);
  const [privLoading, setPrivLoading] = useState(false);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [tab, setTab]           = useState("mapa");
  const [search, setSearch]     = useState("");
  const [filtroUF, setFiltroUF] = useState("");
  const [filtroBioma, setFiltroBioma] = useState("");

  const [w1,setW1] = useState(0.25);
  const [w2,setW2] = useState(0.25);
  const [w3,setW3] = useState(0.25);
  const [w4,setW4] = useState(0.25);
  const [simResult, setSimResult] = useState(null);
  const [simLoading, setSimLoading] = useState(false);

  const total = +(w1+w2+w3+w4).toFixed(4);
  const weightsOk = Math.abs(total-1.0) < 0.02;

  const loadAll = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const params = new URLSearchParams();
      if (filtroUF)    params.set("uf", filtroUF);
      if (filtroBioma) params.set("bioma", filtroBioma);
      const qs = params.toString() ? "?" + params : "";

      const [rRes, mRes, mapRes, bRes, rReq, fRes, sRes] = await Promise.all([
        fetch(`${API}/ranking?top=100${qs ? "&" + params : ""}`),
        fetch(`${API}/municipios${qs}`),
        fetch(`${API}/mapa${qs}`),
        fetch(`${API}/biomas`),
        fetch(`${API}/regioes`),
        fetch(`${API}/formula`),
        fetch(`${API}/status`),
      ]);
      setRanking(await rRes.json());
      setMun(await mRes.json());
      setMapaData(await mapRes.json());
      setBiomas(await bRes.json());
      setRegioes(await rReq.json());
      setFormula(await fRes.json());
      setStatus(await sRes.json());
      // Carrega incentivos privados em paralelo (pode demorar mais)
      fetch(`${API}/incentivos-privados?top=100`).then(r => r.json()).then(setPrivados).catch(() => {});
      fetch(`${API}/incentivos-privados/ranking-cruzado?top=50`).then(r => r.json()).then(setCruzado).catch(() => {});
    } catch (e) {
      setError(T.offline);
    } finally {
      setLoading(false);
    }
  }, [filtroUF, filtroBioma]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const simular = async () => {
    if (!weightsOk) return;
    setSimLoading(true);
    try {
      const res = await fetch(`${API}/simular`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ alpha1_desmatamento:w1, alpha2_multas:w2, alpha3_reincidencia:w3, alpha4_embargo:w4, top:100 }),
      });
      setSimResult(await res.json());
    } catch(e) { console.error(e); }
    setSimLoading(false);
  };

  const displayRank = simResult?.ranking || ranking;
  const filtered = displayRank.filter(e =>
    !search || e.municipio?.toLowerCase().includes(search.toLowerCase()) ||
    e.uf?.toLowerCase().includes(search.toLowerCase()) ||
    e.bioma?.toLowerCase().includes(search.toLowerCase())
  );

  const icaeAvg = displayRank.length ? displayRank.reduce((a,b) => a+(b.icae||0), 0)/displayRank.length : null;
  const highCoh = displayRank.filter(d => d.icae >= 0.7).length;
  const lowCoh  = displayRank.filter(d => d.icae < 0.4).length;

  const bins = 10;
  const distData = Array.from({length:bins},(_,i) => {
    const lo=i/bins, hi=(i+1)/bins;
    return { range:`${Math.round(lo*100)}–${Math.round(hi*100)}`, count:displayRank.filter(d=>d.icae>=lo&&d.icae<hi).length, midVal:(lo+hi)/2 };
  });

  const UFS = [...new Set(ranking.map(d=>d.uf).filter(Boolean))].sort();
  const BIOMAS_LIST = [...new Set(ranking.map(d=>d.bioma).filter(Boolean))].sort();

  const tabs = [
    {id:"mapa",     label:T.tabMap},
    {id:"overview", label:T.tabOverview},
    {id:"ranking",  label:T.tabRanking},
    {id:"scatter",  label:T.tabScatter},
    {id:"privados", label:T.tabPrivate},
    {id:"biomas",   label:T.tabBiomes},
    {id:"simulator",label:T.tabSim},
    {id:"como",     label:T.tabHow},
  ];

  return (
    <div style={{ minHeight:"100vh", background:C.bg, color:C.text, fontFamily:"'DM Sans',sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap');
        *{box-sizing:border-box;margin:0;padding:0}
        ::-webkit-scrollbar{width:6px;height:6px}
        ::-webkit-scrollbar-track{background:${C.bg}}
        ::-webkit-scrollbar-thumb{background:${C.border};border-radius:3px}
        .tab-btn{background:none;border:none;cursor:pointer;transition:all 0.2s}
        .tab-btn:hover{color:${C.accent}!important}
        .row-hover:hover{background:#1a2535!important}
        @keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
        .fade-in{animation:fadeIn 0.4s ease both}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
        .pulse{animation:pulse 1.5s ease infinite}
        select{background:${C.card};border:1px solid ${C.border};color:${C.text};border-radius:8px;padding:6px 10px;font-size:12px;outline:none}
        input[type=range]{height:4px;border-radius:2px}
      `}</style>

      {/* Header */}
      <header style={{ borderBottom:`1px solid ${C.border}`, padding:"0 32px", display:"flex", alignItems:"center", justifyContent:"space-between", height:60, position:"sticky", top:0, zIndex:100, background:`${C.bg}ee`, backdropFilter:"blur(12px)" }}>
        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          <div style={{ width:34, height:34, borderRadius:8, background:`linear-gradient(135deg,${C.accent},#00b8d4)`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:16 }}>🌿</div>
          <div>
            <div style={{ fontFamily:"Syne", fontWeight:800, fontSize:16, letterSpacing:"-0.02em" }}>ICAE Brasil</div>
            <div style={{ fontSize:9, color:C.textDim, fontFamily:"DM Mono", letterSpacing:"0.06em" }}>{T.appSubtitle}</div>
          </div>
        </div>

        <div style={{ display:"flex", gap:2 }}>
          {tabs.map(t => (
            <button key={t.id} className="tab-btn" onClick={() => setTab(t.id)} style={{ padding:"5px 12px", borderRadius:6, fontSize:11, color:tab===t.id?C.accent:C.textDim, background:tab===t.id?C.accentDim:"transparent" }}>{t.label}</button>
          ))}
        </div>

        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          {/* Filtros globais */}
          <select value={filtroUF} onChange={e=>{setFiltroUF(e.target.value)}}>
            <option value="">{T.allStates}</option>
            {UFS.map(u => <option key={u} value={u}>{u}</option>)}
          </select>
          <select value={filtroBioma} onChange={e=>{setFiltroBioma(e.target.value)}}>
            <option value="">{T.allBiomes}</option>
            {BIOMAS_LIST.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
          <div style={{ display:"flex", alignItems:"center", gap:6 }}>
            <div style={{ width:7, height:7, borderRadius:"50%", background:error?C.warn:C.accent, boxShadow:error?`0 0 8px ${C.warn}`:`0 0 8px ${C.accent}` }} />
            <span style={{ fontSize:10, color:C.textDim, fontFamily:"DM Mono" }}>
              {status?.carregando?T.updating:error?T.offline:`${status?.fonte?.toUpperCase()||"DEMO"}`}
            </span>
          </div>
          <button onClick={() => setLang(l => l === "pt" ? "en" : "pt")}
            style={{ padding:"4px 10px", background:C.card, border:`1px solid ${C.border}`, borderRadius:6, color:C.textDim, fontSize:11, cursor:"pointer", fontFamily:"DM Mono", letterSpacing:"0.05em" }}>
            {T.langToggle}
          </button>
        </div>
      </header>

      <main style={{ padding:"28px 32px", maxWidth:1440, margin:"0 auto" }}>
        {error && <div style={{ background:C.warnDim, border:`1px solid ${C.warn}`, borderRadius:10, padding:"12px 16px", marginBottom:20, color:C.warn, fontSize:13 }}>⚠️ {error}</div>}
        {status?.carregando && !loading && (
          <div style={{ background:"#0a1a2a", border:`1px solid #00b8d440`, borderRadius:10, padding:"10px 16px", marginBottom:16, color:"#00b8d4", fontSize:12, display:"flex", alignItems:"center", gap:10 }}>
            <span className="pulse">⏳</span>
            {lang === "pt"
              ? "Sincronizando dados reais com SICOR/BCB e PRODES/INPE… Isso pode levar 2–5 minutos. Os dados exibidos são temporários."
              : "Syncing real data from SICOR/BCB and PRODES/INPE… This may take 2–5 minutes. Displayed data is temporary."}
          </div>
        )}
        {loading && <div style={{ textAlign:"center", padding:80, color:C.textDim, fontFamily:"DM Mono" }}><div className="pulse">{T.mapLoading}</div></div>}

        {!loading && !error && (
          <div className="fade-in">

            {/* ── MAPA ── */}
            {tab === "mapa" && (
              <div>
                <div style={{ marginBottom:20 }}>
                  <h1 style={{ fontFamily:"Syne", fontSize:30, fontWeight:800, letterSpacing:"-0.03em" }}>{T.mapTitle}</h1>
                  <p style={{ color:C.textDim, fontSize:13, marginTop:8, maxWidth:680, lineHeight:1.6 }}>
                    {T.mapDesc}
                  </p>
                </div>

                <MapaBrasil dados={mapaData} filtroUF={filtroUF} onMunicipioClick={uf => setFiltroUF(uf === filtroUF ? "" : uf)} T={T} />

                {/* Top desmatadores */}
                <div style={{ marginTop:20, display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
                  <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:20 }}>
                    <div style={{ fontFamily:"Syne", fontWeight:700, marginBottom:12 }}>{T.listDeforest}</div>
                    {[...mapaData].sort((a,b) => (b.delta_km2||0)-(a.delta_km2||0)).slice(0,8).map((d,i) => (
                      <div key={i} style={{ display:"flex", justifyContent:"space-between", padding:"6px 0", borderBottom:`1px solid ${C.border}20`, fontSize:13 }}>
                        <span style={{ color:C.textDim }}><span style={{ color:C.muted, fontFamily:"DM Mono", fontSize:11, marginRight:8 }}>{i+1}</span>{d.municipio || d.uf}</span>
                        <span style={{ color:C.warn, fontFamily:"DM Mono" }}>+{(d.delta_km2||0).toFixed(0)} km²</span>
                      </div>
                    ))}
                  </div>

                  <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:20 }}>
                    <div style={{ fontFamily:"Syne", fontWeight:700, marginBottom:12 }}>{T.listCredit}</div>
                    {[...mapaData].filter(d=>d.risk>0.5).sort((a,b)=>(b.credito||0)-(a.credito||0)).slice(0,8).map((d,i) => (
                      <div key={i} style={{ display:"flex", justifyContent:"space-between", padding:"6px 0", borderBottom:`1px solid ${C.border}20`, fontSize:13 }}>
                        <span style={{ color:C.textDim }}><span style={{ color:C.muted, fontFamily:"DM Mono", fontSize:11, marginRight:8 }}>{i+1}</span>{d.municipio || d.uf}</span>
                        <span style={{ color:C.warn, fontFamily:"DM Mono", fontSize:11 }}>R${((d.credito||0)/1e6).toFixed(1)}M · {icaeLabel(d.icae,T)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ── OVERVIEW ── */}
            {tab === "overview" && (
              <div>
                <div style={{ marginBottom:28 }}>
                  <h1 style={{ fontFamily:"Syne", fontSize:32, fontWeight:800, letterSpacing:"-0.03em" }}>{T.overviewTitle}</h1>
                  <p style={{ color:C.textDim, marginTop:8, maxWidth:680, fontSize:14, lineHeight:1.6 }}>
                    {T.overviewDesc}
                    {status?.fonte === "real" ? T.realData : T.demoData}
                  </p>
                </div>

                <div style={{ display:"flex", gap:14, marginBottom:24, flexWrap:"wrap" }}>
                  <KpiCard label={T.kpiMun} value={displayRank.length} sub={T.kpiMunSub}
                    tooltip={T.kpiMunTip} />
                  <KpiCard label={T.kpiScore} value={icaeAvg!==null?`${(icaeAvg*100).toFixed(0)}/100`:"–"}
                    sub={icaeAvg!==null?icaeLabel(icaeAvg,T):""} accent={icaeAvg!==null?icaeColor(icaeAvg):C.accent}
                    tooltip="Média nacional de coerência entre uso do crédito público e conduta ambiental." />
                  <KpiCard label={T.kpiResp} value={highCoh} sub={T.kpiRespSub} accent={C.accent} />
                  <KpiCard label={T.kpiCrit} value={lowCoh} sub={T.kpiCritSub} accent={C.warn}
                    tooltip={T.kpiCritTip} />
                </div>

                <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginBottom:16 }}>
                  <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:22 }}>
                    <div style={{ fontFamily:"Syne", fontWeight:700, marginBottom:4 }}>{T.chartScores}</div>
                    <div style={{ fontSize:12, color:C.textDim, marginBottom:16 }}>{T.chartScoresSub}</div>
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={distData} barCategoryGap="20%">
                        <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
                        <XAxis dataKey="range" tick={{ fill:C.textDim, fontSize:10 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fill:C.textDim, fontSize:10 }} axisLine={false} tickLine={false} />
                        <Bar dataKey="count" radius={[4,4,0,0]}>
                          {distData.map((d,i) => <Cell key={i} fill={icaeColor(d.midVal)} fillOpacity={0.85} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:22 }}>
                    <div style={{ fontFamily:"Syne", fontWeight:700, marginBottom:4 }}>{T.chartBiomes}</div>
                    <div style={{ fontSize:12, color:C.textDim, marginBottom:16 }}>{T.chartBiomesSub}</div>
                    <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
                      {biomas.map(b => (
                        <div key={b.bioma} style={{ display:"flex", alignItems:"center", gap:12 }}>
                          <div style={{ width:12, height:12, borderRadius:2, background:BIOMA_COR[b.bioma]||C.muted, flexShrink:0 }} />
                          <div style={{ flex:1 }}>
                            <div style={{ display:"flex", justifyContent:"space-between", marginBottom:3 }}>
                              <span style={{ fontSize:12 }}>{b.bioma}</span>
                              <span style={{ fontSize:12, color:icaeColor(b.icae_medio||0), fontFamily:"DM Mono" }}>{((b.icae_medio||0)*100).toFixed(0)}/100</span>
                            </div>
                            <div style={{ width:"100%", height:4, background:C.border, borderRadius:2 }}>
                              <div style={{ width:`${(b.icae_medio||0)*100}%`, height:"100%", background:icaeColor(b.icae_medio||0), borderRadius:2 }} />
                            </div>
                          </div>
                          <span style={{ fontSize:10, color:C.textDim, fontFamily:"DM Mono", width:60, textAlign:"right" }}>
                            {b.n_municipios} {T.munLabel}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:22 }}>
                  <div style={{ fontFamily:"Syne", fontWeight:700, marginBottom:4 }}>{T.chartRegions}</div>
                  <div style={{ fontSize:12, color:C.textDim, marginBottom:16 }}>{T.chartRegionsSub}</div>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={regioes}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
                      <XAxis dataKey="regiao" tick={{ fill:C.textDim, fontSize:11 }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0,1]} tickFormatter={v=>`${(v*100).toFixed(0)}`} tick={{ fill:C.textDim, fontSize:10 }} axisLine={false} tickLine={false} />
                      <ReferenceLine y={0.5} stroke={C.accent} strokeDasharray="6 3" strokeOpacity={0.4} />
                      <Tooltip content={<CustomTooltip T={T} />} cursor={{ fill:C.border }} />
                      <Bar dataKey="icae_medio" radius={[4,4,0,0]}>
                        {regioes.map((d,i) => <Cell key={i} fill={icaeColor(d.icae_medio||0)} fillOpacity={0.85} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* ── RANKING ── */}
            {tab === "ranking" && (
              <div>
                <div style={{ display:"flex", alignItems:"center", gap:14, marginBottom:20, flexWrap:"wrap" }}>
                  <h2 style={{ fontFamily:"Syne", fontWeight:800, fontSize:26 }}>{T.rankTitle}</h2>
                  <input placeholder={T.rankSearch} value={search} onChange={e=>setSearch(e.target.value)}
                    style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:8, padding:"8px 14px", color:C.text, fontSize:13, width:320, outline:"none" }} />
                  <div style={{ color:C.textDim, fontSize:12, fontFamily:"DM Mono" }}>{filtered.length} {T.rankMuns}</div>
                </div>

                <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, overflow:"hidden" }}>
                  <div style={{ display:"grid", gridTemplateColumns:"50px 1fr 60px 80px 160px 90px 100px 120px", padding:"10px 18px", borderBottom:`1px solid ${C.border}`, fontSize:10, color:C.textDim, textTransform:"uppercase", letterSpacing:"0.1em" }}>
                    <span>{T.colRank}</span><span>{T.colMun}</span><span>{T.colUF}</span><span>{T.colBiome}</span><span>{T.colScore}</span><span>{T.colBar}</span><span>{T.colRisk}</span><span>{T.colStatus}</span>
                  </div>
                  <div style={{ maxHeight:580, overflowY:"auto" }}>
                    {(() => {
                      const munCount = {};
                      const munIdx = {};
                      filtered.forEach(e => { const k=`${e.municipio}-${e.uf}`; munCount[k]=(munCount[k]||0)+1; });
                      return filtered.map((e,i) => {
                        const k=`${e.municipio}-${e.uf}`;
                        const isMulti = munCount[k] > 1;
                        munIdx[k] = (munIdx[k]||0)+1;
                        const prodN = isMulti ? munIdx[k] : null;
                        return (
                      <div key={e.entity_id} className="row-hover" style={{ display:"grid", gridTemplateColumns:"50px 1fr 60px 80px 160px 90px 100px 120px", padding:"11px 18px", alignItems:"center", borderBottom:`1px solid ${C.border}20`, fontSize:12 }}>
                        <span style={{ color:C.muted, fontFamily:"DM Mono", fontSize:10 }}>{e.rank||i+1}</span>
                        <div>
                          <div style={{ fontWeight:500 }}>{e.municipio}{prodN && <span style={{ marginLeft:8, fontSize:10, color:C.muted, fontFamily:"DM Mono", background:C.surface, border:`1px solid ${C.border}`, borderRadius:4, padding:"1px 6px" }}>{T.prodLabel} {prodN}</span>}</div>
                          {e.regiao && <div style={{ fontSize:10, color:C.textDim }}>{e.regiao}</div>}
                        </div>
                        <span style={{ fontFamily:"DM Mono", fontSize:11, color:C.textDim }}>{e.uf}</span>
                        <span style={{ fontSize:10, color:BIOMA_COR[e.bioma]||C.textDim }}>
                          <span style={{ display:"inline-block", width:8, height:8, borderRadius:"50%", background:BIOMA_COR[e.bioma]||C.muted, marginRight:4 }} />{e.bioma?.split(" ")[0]}
                        </span>
                        <span style={{ fontFamily:"DM Mono", fontWeight:700, color:icaeColor(e.icae), fontSize:15 }}>{(e.icae*100).toFixed(0)}</span>
                        <div><ScoreBar value={e.icae} /></div>
                        <span style={{ fontSize:11, color:e.risk>0.6?C.warn:C.textDim }}>
                          {e.risk>0.6?T.riskHigh:e.risk>0.3?T.riskMed:T.riskLow}
                        </span>
                        <span style={{ fontSize:11, color:icaeColor(e.icae) }}>{icaeLabel(e.icae,T)}</span>
                      </div>
                        );
                      });
                    })()}
                  </div>
                </div>
              </div>
            )}

            {/* ── SCATTER ── */}
            {tab === "scatter" && (
              <div>
                <div style={{ marginBottom:22 }}>
                  <h2 style={{ fontFamily:"Syne", fontWeight:800, fontSize:26 }}>{T.scatterTitle}</h2>
                  <p style={{ color:C.textDim, fontSize:13, marginTop:6, maxWidth:680, lineHeight:1.6 }}>
                    {T.scatterDesc}
                  </p>
                </div>
                <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:24 }}>
                  <ResponsiveContainer width="100%" height={460}>
                    <ScatterChart margin={{ top:20, right:30, bottom:30, left:10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                      <XAxis type="number" dataKey="credito_norm" name="Crédito" domain={[0,1]} tickFormatter={v=>`${(v*100).toFixed(0)}%`}
                        label={{ value:T.axisCredit, position:"insideBottom", offset:-16, fill:C.muted, fontSize:11 }}
                        tick={{ fill:C.textDim, fontSize:10 }} axisLine={false} tickLine={false} />
                      <YAxis type="number" dataKey="risk" name="Risco" domain={[0,1]} tickFormatter={v=>`${(v*100).toFixed(0)}%`}
                        label={{ value:T.axisRisk, angle:-90, position:"insideLeft", offset:16, fill:C.muted, fontSize:11 }}
                        tick={{ fill:C.textDim, fontSize:10 }} axisLine={false} tickLine={false} />
                      <Tooltip content={<CustomTooltip T={T} />} cursor={{ strokeDasharray:"3 3" }} />
                      <ReferenceLine x={0.5} stroke={C.muted} strokeDasharray="6 3" strokeOpacity={0.5} />
                      <ReferenceLine y={0.5} stroke={C.muted} strokeDasharray="6 3" strokeOpacity={0.5} />
                      <Scatter data={filtered} shape={(props) => {
                        const { cx, cy, payload } = props;
                        const col = BIOMA_COR[payload.bioma] || icaeColor(payload.icae);
                        const r = 4 + Math.sqrt((payload.credito_norm||0) * 16);
                        return <circle cx={cx} cy={cy} r={r} fill={col} fillOpacity={0.75} stroke={col} strokeWidth={0.5} />;
                      }} />
                    </ScatterChart>
                  </ResponsiveContainer>
                  <div style={{ display:"flex", gap:12, marginTop:12, flexWrap:"wrap" }}>
                    {Object.entries(BIOMA_COR).map(([b,c]) => (
                      <div key={b} style={{ display:"flex", alignItems:"center", gap:4, fontSize:11, color:C.textDim }}>
                        <div style={{ width:10, height:10, borderRadius:"50%", background:c }} />{b}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ── INCENTIVOS PRIVADOS ── */}
            {tab === "privados" && (
              <div>
                <div style={{ marginBottom:24 }}>
                  <h2 style={{ fontFamily:"Syne", fontWeight:800, fontSize:26 }}>{T.privTitle}</h2>
                  <p style={{ color:C.textDim, fontSize:13, marginTop:6, maxWidth:720, lineHeight:1.6 }}>
                    {T.privDesc}
                  </p>
                  <div style={{ display:"flex", gap:8, marginTop:12 }}>
                    {[
                      {l:"🏦 BNDES", d:"Desembolsos agronegócio — CSV público (dadosabertos.bndes.gov.br)", c:C.accent},
                      {l:"📦 Comex Stat", d:"Exportações soja, boi, madeira etc — API pública MDIC", c:"#7c3aed"},
                      {l:"💵 SICOR/BCB", d:"Crédito rural Pronaf/ABC — já no ICAE principal", c:C.textDim},
                    ].map(b => (
                      <div key={b.l} style={{ background:C.card, border:`1px solid ${b.c}40`, borderRadius:8, padding:"8px 14px", fontSize:11, color:C.textDim }}>
                        <span style={{ color:b.c, fontWeight:700 }}>{b.l}</span> — {b.d}
                      </div>
                    ))}
                  </div>
                </div>

                {privados.length === 0 && (
                  <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:40, textAlign:"center", color:C.textDim }}>
                    <div style={{ fontSize:28, marginBottom:12 }}>⏳</div>
                    <div style={{ fontFamily:"Syne", fontSize:16, marginBottom:8 }}>{T.privLoading}</div>
                    <div style={{ fontSize:12 }}>{T.privLoadSub}</div>
                    <button onClick={() => {
                      setPrivLoading(true);
                      fetch(`${API}/incentivos-privados/atualizar`, {method:"POST"})
                        .then(() => setTimeout(() => {
                          fetch(`${API}/incentivos-privados?top=100`).then(r=>r.json()).then(setPrivados);
                          fetch(`${API}/incentivos-privados/ranking-cruzado?top=50`).then(r=>r.json()).then(setCruzado);
                          setPrivLoading(false);
                        }, 3000))
                        .catch(() => setPrivLoading(false));
                    }} style={{ marginTop:16, padding:"10px 24px", background:C.accent, border:"none", borderRadius:8, color:"#0a0e1a", fontWeight:700, cursor:"pointer", fontSize:13 }}>
                      {privLoading ? T.privUpdating : T.privForce}
                    </button>
                  </div>
                )}

                {privados.length > 0 && (
                  <div style={{ display:"grid", gap:16 }}>

                    {/* Aviso dados demo */}
                    {privados[0]?.codigo_ibge && privados[0].codigo_ibge > 1100000 && privados[0].codigo_ibge < 5300000 &&
                     privados.every(p => p.fonte === undefined) && (
                      <div style={{ background:"#2a1f00", border:`1px solid ${C.warn}`, borderRadius:10, padding:"10px 16px", color:C.warn, fontSize:12, display:"flex", alignItems:"center", gap:8 }}>
                        ⚠️ {lang === "pt"
                          ? "Exibindo dados demo — integração BNDES/Comex Stat ainda em validação. Os valores não refletem dados reais."
                          : "Showing demo data — BNDES/Comex Stat integration still under validation. Values do not reflect real data."}
                      </div>
                    )}

                    {/* KPIs */}
                    <div style={{ display:"flex", gap:14, flexWrap:"wrap" }}>
                      {[
                        {l:T.kpiPrivMun, v:privados.length, c:C.accent},
                        {l:T.kpiBNDES, v:fmtBRL(privados.reduce((a,b)=>a+(b.bndes_valor_reais||0),0)), c:"#00b8d4"},
                        {l:T.kpiComex, v:fmtUSD(privados.reduce((a,b)=>a+(b.comex_valor_usd||0),0)), c:"#7c3aed"},
                        {l:T.kpiPrivTotal, v:fmtBRL(privados.reduce((a,b)=>a+(b.incentivo_privado_total_reais||0),0)), c:C.warn},
                      ].map(k => (
                        <KpiCard key={k.l} label={k.l} value={k.v} accent={k.c} />
                      ))}
                    </div>

                    {/* Ranking BNDES */}
                    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
                      <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:20 }}>
                        <div style={{ fontFamily:"Syne", fontWeight:700, marginBottom:4 }}>{T.topBNDES}</div>
                        <div style={{ fontSize:11, color:C.textDim, marginBottom:14 }}>{T.topBNDESSub}</div>
                        {[...privados].sort((a,b)=>(b.bndes_valor_reais||0)-(a.bndes_valor_reais||0)).slice(0,10).map((d,i) => (
                          <div key={i} style={{ display:"flex", justifyContent:"space-between", padding:"7px 0", borderBottom:`1px solid ${C.border}20`, fontSize:12 }}>
                            <span><span style={{ color:C.muted, fontFamily:"DM Mono", fontSize:10, marginRight:8 }}>{i+1}</span>{d.municipio} <span style={{ color:C.textDim, fontSize:10 }}>{d.uf}</span></span>
                            <span style={{ color:"#00b8d4", fontFamily:"DM Mono" }}>{fmtBRL(d.bndes_valor_reais||0)}</span>
                          </div>
                        ))}
                      </div>

                      <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:20 }}>
                        <div style={{ fontFamily:"Syne", fontWeight:700, marginBottom:4 }}>{T.topComex}</div>
                        <div style={{ fontSize:11, color:C.textDim, marginBottom:14 }}>{T.topComexSub}</div>
                        {[...privados].sort((a,b)=>(b.comex_valor_usd||0)-(a.comex_valor_usd||0)).slice(0,10).map((d,i) => (
                          <div key={i} style={{ display:"flex", justifyContent:"space-between", padding:"7px 0", borderBottom:`1px solid ${C.border}20`, fontSize:12 }}>
                            <div>
                              <span style={{ color:C.muted, fontFamily:"DM Mono", fontSize:10, marginRight:8 }}>{i+1}</span>
                              {d.municipio} <span style={{ color:C.textDim, fontSize:10 }}>{d.uf}</span>
                              {d.produto_principal && <span style={{ color:"#7c3aed", fontSize:10, marginLeft:6 }}>· {d.produto_principal}</span>}
                            </div>
                            <span style={{ color:"#7c3aed", fontFamily:"DM Mono" }}>{fmtUSD(d.comex_valor_usd||0)}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Ranking cruzado — os casos mais críticos */}
                    {cruzado.length > 0 && (
                      <div style={{ background:C.card, border:`1px solid ${C.warn}30`, borderRadius:12, padding:20, borderTop:`2px solid ${C.warn}` }}>
                        <div style={{ fontFamily:"Syne", fontWeight:700, marginBottom:4 }}>{T.critTitle}</div>
                        <div style={{ fontSize:11, color:C.textDim, marginBottom:16 }}>
                          {T.critDesc}
                        </div>

                        <div style={{ display:"grid", gridTemplateColumns:"40px 1fr 50px 80px 110px 110px 110px 110px 100px", padding:"8px 0", borderBottom:`1px solid ${C.border}`, fontSize:10, color:C.muted, textTransform:"uppercase", letterSpacing:"0.08em" }}>
                          <span>#</span><span>{T.colMun}</span><span>{T.colUF}</span><span>{T.colBiome}</span><span>{T.colPubCredit}</span><span>{T.colBNDES}</span><span>{T.colExports}</span><span>{T.colDeforest}</span><span>ICAE</span>
                        </div>
                        <div style={{ maxHeight:420, overflowY:"auto" }}>
                          {cruzado.map((d,i) => (
                            <div key={i} className="row-hover" style={{ display:"grid", gridTemplateColumns:"40px 1fr 50px 80px 110px 110px 110px 110px 100px", padding:"10px 0", alignItems:"center", borderBottom:`1px solid ${C.border}15`, fontSize:11 }}>
                              <span style={{ color:C.muted, fontFamily:"DM Mono", fontSize:10 }}>{i+1}</span>
                              <div>
                                <div style={{ fontWeight:500 }}>{d.municipio}</div>
                                {d.produto_principal && <div style={{ fontSize:10, color:"#7c3aed" }}>{d.produto_principal}</div>}
                              </div>
                              <span style={{ fontFamily:"DM Mono", fontSize:10, color:C.textDim }}>{d.uf}</span>
                              <span style={{ fontSize:10, color:C.textDim }}>{d.bioma?.split(" ")[0]}</span>
                              <span style={{ fontFamily:"DM Mono", fontSize:10 }}>{fmtBRL(d.credito||0)}</span>
                              <span style={{ fontFamily:"DM Mono", fontSize:10, color:"#00b8d4" }}>{fmtBRL(d.bndes_valor_reais||0)}</span>
                              <span style={{ fontFamily:"DM Mono", fontSize:10, color:"#7c3aed" }}>{fmtUSD(d.comex_valor_usd||0)}</span>
                              <span style={{ fontFamily:"DM Mono", fontSize:10, color:C.warn }}>+{(d.delta_km2||0).toFixed(0)} km²</span>
                              <span style={{ fontFamily:"DM Mono", fontSize:12, fontWeight:700, color:icaeColor(d.icae||0) }}>{((d.icae||0)*100).toFixed(0)}/100</span>
                            </div>
                          ))}
                        </div>
                        <div style={{ marginTop:12, fontSize:11, color:C.textDim, fontStyle:"italic" }}>
                          ⚠️ Importante: exportações representam receita, não necessariamente incentivo direto — mas indicam o retorno financeiro que torna economicamente racional o desmatamento.
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── BIOMAS ── */}
            {tab === "biomas" && (
              <div>
                <h2 style={{ fontFamily:"Syne", fontWeight:800, fontSize:26, marginBottom:8 }}>{T.biomesTitle}</h2>
                <p style={{ color:C.textDim, fontSize:13, marginBottom:24 }}>{T.biomesSub}</p>
                <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(280px,1fr))", gap:14 }}>
                  {biomas.map(b => (
                    <div key={b.bioma} style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:20, borderLeft:`3px solid ${BIOMA_COR[b.bioma]||C.accent}` }}>
                      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:12 }}>
                        <div style={{ fontFamily:"Syne", fontWeight:700, fontSize:15 }}>{b.bioma}</div>
                        <div style={{ background:icaeColor(b.icae_medio||0)+"22", color:icaeColor(b.icae_medio||0), borderRadius:6, padding:"3px 10px", fontSize:11, fontWeight:700 }}>
                          {icaeLabel(b.icae_medio||0,T)}
                        </div>
                      </div>
                      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>
                        {[
                          {l:T.kpiAvgScore,v:`${((b.icae_medio||0)*100).toFixed(0)}/100`,c:icaeColor(b.icae_medio||0)},
                          {l:T.kpiMunCount,v:b.n_municipios,c:C.text},
                          {l:T.kpiDeforest,v:`${(b.delta_km2_total||0)>=1000?((b.delta_km2_total)/1000).toFixed(1)+"k":(b.delta_km2_total||0).toFixed(0)} km²`,c:C.warn},
                          {l:T.kpiCreditTot,v:fmtBRL(b.credito_total||0),c:C.accent},
                        ].map(s => (
                          <div key={s.l} style={{ background:C.bg, borderRadius:6, padding:"8px 10px" }}>
                            <div style={{ fontSize:9, color:C.muted, textTransform:"uppercase", letterSpacing:"0.08em" }}>{s.l}</div>
                            <div style={{ fontSize:16, fontWeight:700, color:s.c, fontFamily:"Syne" }}>{s.v}</div>
                          </div>
                        ))}
                      </div>
                      <div style={{ marginTop:12 }}>
                        <ScoreBar value={b.icae_medio||0} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── SIMULADOR ── */}
            {tab === "simulator" && (
              <div>
                <div style={{ marginBottom:20 }}>
                  <h2 style={{ fontFamily:"Syne", fontWeight:800, fontSize:26 }}>{T.simTitle}</h2>
                  <p style={{ color:C.textDim, fontSize:13, marginTop:6, maxWidth:680, lineHeight:1.6 }}>{T.simDesc}</p>
                </div>
                <div style={{ display:"grid", gridTemplateColumns:"340px 1fr", gap:20 }}>
                  <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:22, alignSelf:"start" }}>
                    <div style={{ fontFamily:"Syne", fontWeight:700, fontSize:16, marginBottom:18 }}>{T.simTitle}</div>
                    {[
                      {l:T.simDeforest,d:T.simDeforestD,v:w1,fn:setW1},
                      {l:T.simFines,d:T.simFinesD,v:w2,fn:setW2},
                      {l:T.simRecid,d:T.simRecidD,v:w3,fn:setW3},
                      {l:T.simEmbargo,d:T.simEmbargoD,v:w4,fn:setW4},
                    ].map(s => (
                      <div key={s.l} style={{ marginBottom:18 }}>
                        <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
                          <span style={{ fontSize:13, fontWeight:500 }}>{s.l}</span>
                          <span style={{ color:C.accent, fontFamily:"DM Mono", fontSize:13 }}>{Math.round(s.v*100)}%</span>
                        </div>
                        <div style={{ fontSize:11, color:C.textDim, marginBottom:6 }}>{s.d}</div>
                        <input type="range" min={0} max={1} step={0.05} value={s.v} onChange={e=>s.fn(parseFloat(e.target.value))}
                          style={{ width:"100%", accentColor:C.accent, cursor:"pointer" }} />
                      </div>
                    ))}
                    <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"10px 0", borderTop:`1px solid ${C.border}` }}>
                      <span style={{ fontSize:13, color:C.textDim }}>{T.simTotal}</span>
                      <span style={{ fontFamily:"DM Mono", fontSize:20, fontWeight:700, color:weightsOk?C.accent:C.warn }}>{Math.round(total*100)}%</span>
                    </div>
                    {!weightsOk && <div style={{ color:C.warn, fontSize:12, marginBottom:10 }}>{T.simWarning}</div>}
                    <button onClick={simular} disabled={!weightsOk||simLoading} style={{ width:"100%", padding:"12px 0", borderRadius:8, border:"none", background:weightsOk?C.accent:C.muted, color:"#0a0e1a", fontWeight:700, fontSize:13, cursor:weightsOk?"pointer":"not-allowed", marginTop:8 }}>
                      {simLoading?T.simCalc:T.simBtn}
                    </button>
                    {simResult && (
                      <div style={{ marginTop:14, padding:12, background:C.accentDim, borderRadius:8, border:`1px solid ${C.accent}30` }}>
                        <div style={{ fontSize:10, color:C.accent, textTransform:"uppercase", letterSpacing:"0.08em" }}>{T.simAvg}</div>
                        <div style={{ fontFamily:"Syne", fontSize:26, fontWeight:800, color:C.accent, marginTop:4 }}>
                          {(simResult.icae_medio*100).toFixed(1)}<span style={{ fontSize:13 }}>/100</span>
                        </div>
                      </div>
                    )}
                  </div>
                  <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:22 }}>
                    <div style={{ fontFamily:"Syne", fontWeight:700, fontSize:16, marginBottom:16 }}>
                      {simResult?T.simRankTitle:T.simRankDef}{T.simTop20}
                    </div>
                    <ResponsiveContainer width="100%" height={460}>
                      <BarChart data={(simResult?.ranking||ranking).slice(0,20)} layout="vertical" barCategoryGap="15%">
                        <CartesianGrid strokeDasharray="3 3" stroke={C.border} horizontal={false} />
                        <XAxis type="number" domain={[0,1]} tickFormatter={v=>`${(v*100).toFixed(0)}`} tick={{ fill:C.textDim, fontSize:10 }} axisLine={false} tickLine={false} />
                        <YAxis type="category" dataKey="municipio" tick={{ fill:C.textDim, fontSize:9 }} axisLine={false} tickLine={false} width={100} />
                        <Tooltip content={<CustomTooltip T={T} />} cursor={{ fill:C.border }} />
                        <Bar dataKey="icae" radius={[0,4,4,0]}>
                          {(simResult?.ranking||ranking).slice(0,20).map((d,i) => <Cell key={i} fill={icaeColor(d.icae)} fillOpacity={0.85} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}

            {/* ── COMO FUNCIONA ── */}
            {tab === "como" && (
              <div style={{ maxWidth:740 }}>
                <h2 style={{ fontFamily:"Syne", fontWeight:800, fontSize:28, marginBottom:8 }}>{T.howTitle}</h2>
                <p style={{ color:C.textDim, fontSize:14, marginBottom:28, lineHeight:1.7 }}>
                  {T.howDesc}
                </p>

                {[
                  {icon:"💰",t:T.howQ1,d:T.howA1},
                  {icon:"🌳",t:T.howQ2,d:T.howA2},
                  {icon:"🔗",t:T.howQ3,d:T.howA3},
                  {icon:"📊",t:T.howQ4,d:T.howA4},
                ].map(s => (
                  <div key={s.t} style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:22, marginBottom:12, display:"flex", gap:16 }}>
                    <div style={{ width:44, height:44, borderRadius:10, background:C.accentDim, border:`1px solid ${C.accent}30`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:22, flexShrink:0 }}>{s.icon}</div>
                    <div>
                      <div style={{ fontFamily:"Syne", fontWeight:700, marginBottom:6 }}>{s.t}</div>
                      <div style={{ fontSize:13, color:C.textDim, lineHeight:1.6 }}>{s.d}</div>
                    </div>
                  </div>
                ))}

                <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:22, marginTop:4 }}>
                  <div style={{ fontFamily:"Syne", fontWeight:700, marginBottom:14 }}>{T.formulaTitle}</div>
                  {[
                    {n:T.step1n,c:C.accent,eq:T.step1eq,d:T.step1d},
                    {n:T.step2n,c:"#f9c74f",eq:T.step2eq,d:T.step2d},
                    {n:T.step3n,c:C.warn,eq:T.step3eq,d:T.step3d},
                  ].map(p => (
                    <div key={p.n} style={{ display:"flex", gap:14, marginBottom:14, alignItems:"flex-start" }}>
                      <div style={{ width:4, height:"100%", minHeight:40, background:p.c, borderRadius:2, flexShrink:0 }} />
                      <div>
                        <div style={{ fontSize:10, color:C.muted, textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:3 }}>{p.n}</div>
                        <div style={{ fontFamily:"DM Mono", fontSize:13, color:p.c, marginBottom:4 }}>{p.eq}</div>
                        <div style={{ fontSize:12, color:C.textDim }}>{p.d}</div>
                      </div>
                    </div>
                  ))}
                </div>

                <div style={{ marginTop:16, padding:14, borderRadius:10, border:`1px solid ${C.border}`, background:C.surface, fontSize:12, color:C.textDim, lineHeight:1.7 }}>
                  <strong style={{ color:C.text }}>{T.openSrc}</strong><br/>
                  {T.openSrcSub}<br/>
                  {T.openSrcTag}<span style={{ color:C.accent }}>{T.openSrcSlogan}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
      {/* ‌​‌​‌​‍‌​‌​‌​‍‌​‌​‌​‍‌​‌​‍‌​​‍‌​‌​​‍‌​​​‍‌​​‍‌​‌​​‍‌​​‌‍‌​‌​‍‌​​​‍‌​‌​​‍‌​‌‍‌​​​‍‌​​​‍‌​​​‍‌​​‍‌​‌​​‍‌​​‌‍‌​‌​‍‌​​​‍‌​‌​​‍‌​​‌‍‌​‌​‍‌​​​‍‌​​‌ */}
      <span aria-hidden="true" style={{position:"absolute",width:0,height:0,overflow:"hidden",opacity:0,pointerEvents:"none",userSelect:"none",fontSize:0}}>{atob("TUFERSBCWSBWRU5ERVRUQQ==")}</span>
    </div>
  );
}
