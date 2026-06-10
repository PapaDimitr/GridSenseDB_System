// neo4j/import/seed.cypher
// Constraint — run once at startup

CREATE CONSTRAINT substation_id IF NOT EXISTS
    FOR (s:Substation) REQUIRE s.substation_id IS UNIQUE;
CREATE CONSTRAINT transformer_id IF NOT EXISTS
    FOR (t:Transformer) REQUIRE t.asset_id IS UNIQUE;

// ── Nodes ────────────────────────────────────────────────────────
// Grid Supply Point (top of hierarchy)

CREATE (:GridSupplyPoint {
    gsp_id: "GSP_NORTH", name: "Northern Grid Supply Point",
    voltage_kV: 132, region: "North Metro"
});

// Substations
CREATE (:Substation {
    substation_id: "SS_001", name: "Volos Primary",
    voltage_kV: 11, lat: 39.358, lon: 22.938,
    commissioned_year: 1998
})

// Distribution Transformers
CREATE (:Transformer {
    asset_id: "TX_001_A", rating_kVA: 400,
    manufacturer: "ABB", model: "ONAN-400",
    installed: date("2012-06-15"),
    last_inspection: date("2024-09-01")
});

// Smart Meters (a few representative ones)
CREATE (:SmartMeter { meter_id: "SM_00001", premise_id: "PREM_10001",
    tariff_class: "residential", phase: "single" });

// ── Relationships ────────────────────────────────────────────────
// MATCH before MERGE to avoid duplicates in production scripts
MATCH (g:GridSupplyPoint {gsp_id:"GSP_NORTH"})
MATCH (s:Substation {substation_id:"SS_001"})
CREATE (g)-[:FEEDS {feeder_id:"F_001", voltage_kV:11, length_km:2.4}]->(s);
MATCH (s:Substation {substation_id:"SS_001"})
MATCH (t:Transformer {asset_id:"TX_001_A"})
CREATE (s)-[:SUPPLIES {cable_id:"CB_001", distance_m:320}]->(t);
MATCH (t:Transformer {asset_id:"TX_001_A"})
MATCH (m:SmartMeter {meter_id:"SM_00001"})
CREATE (t)-[:CONNECTS_TO]->(m);

// ── Sample traversal queries (test these work) ───────────────────
// Find all nodes downstream of a substation (up to depth 4)
// MATCH (s:Substation {substation_id:'SS_001'})-[:FEEDS|SUPPLIES|CONNECTS_TO*1..4]->(n)
// RETURN labels(n), n LIMIT 50;
// Find meters sharing a transformer with a given meter
// MATCH (:SmartMeter {meter_id:'SM_00001'})<-[:CONNECTS_TO]-(t:Transformer)-[:CONNECTS_TO]->(peer)
// RETURN peer.meter_id, peer.premise_id;