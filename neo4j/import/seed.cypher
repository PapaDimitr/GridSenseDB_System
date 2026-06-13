// neo4j/import/seed.cypher
// Constraints — idempotent (IF NOT EXISTS)

CREATE CONSTRAINT substation_id IF NOT EXISTS
    FOR (s:Substation) REQUIRE s.substation_id IS UNIQUE;
CREATE CONSTRAINT transformer_id IF NOT EXISTS
    FOR (t:Transformer) REQUIRE t.asset_id IS UNIQUE;

// ── Nodes ────────────────────────────────────────────────────────
// Every node carries a uniform `node_id` so the fault-impact traversal
// can address any node by one property (see routers/grid.py).

CREATE (:GridSupplyPoint {
    node_id: "GSP_NORTH", gsp_id: "GSP_NORTH",
    name: "Northern Grid Supply Point",
    voltage_kV: 132, region: "North Metro"
});

CREATE (:Substation {
    node_id: "SS_001", substation_id: "SS_001", name: "Volos Primary",
    voltage_kV: 11, lat: 39.358, lon: 22.938,
    commissioned_year: 1998
});

CREATE (:Transformer {
    node_id: "TX_001_A", asset_id: "TX_001_A", name: "Transformer TX_001_A",
    rating_kVA: 400, manufacturer: "ABB", model: "ONAN-400",
    installed: date("2012-06-15"),
    last_inspection: date("2024-09-01")
});

CREATE (:SmartMeter {
    node_id: "SM_00001", meter_id: "SM_00001", name: "Meter SM_00001",
    premise_id: "PREM_10001", tariff_class: "residential", phase: "single"
});

// ── Relationships ────────────────────────────────────────────────
MATCH (g:GridSupplyPoint {node_id:"GSP_NORTH"})
MATCH (s:Substation {node_id:"SS_001"})
CREATE (g)-[:FEEDS {feeder_id:"F_001", voltage_kV:11, length_km:2.4}]->(s);

MATCH (s:Substation {node_id:"SS_001"})
MATCH (t:Transformer {node_id:"TX_001_A"})
CREATE (s)-[:SUPPLIES {cable_id:"CB_001", distance_m:320}]->(t);

MATCH (t:Transformer {node_id:"TX_001_A"})
MATCH (m:SmartMeter {node_id:"SM_00001"})
CREATE (t)-[:CONNECTS_TO]->(m);