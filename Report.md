## GridSense final project

### A1
> a)

The strongest technical point in the senior engineer's argmument is that with a single a query you can fetch data from multiple schemas while automatically maintaining ACID qurantees.This is important since there are workflows that require fetching or adding/editting on mulitple databases.For expaple onboarding a new customer and his/her property on the network requires creating a new billing account, adding a smart metter to the topology graph and registering the new equipment in the catalog.If a write fails in one of these you have no native way of rolling back changes in a polyglot architecture.Traditional mechanisms such as Two-phase commit used by Postgre that operates using "partipants and cordinator" mechanism would have to be implemented on higher level from our team to ensure consistency in case of a fault.

> b)

PostgreSQL can be slow for large datasets and multiple partitions.Complexity increases when trying to apply ACID guarantees in distributed system.Considering high throughput of queries from sensor data PostgreSQL database seems unreasonable.
For lets say 100 bytes of data per event we will have 4MB/s*86400 = 345Gb/day which exceeds(by a lot) the default max_threshold for WAL (1GB) meaning that the rate at which the database writes dirty pages will have to aggressively increase to match data throughput.The increased I/O writes from WAL could create a bottleneck to the system and make it more susceptible which is highly unwanted based on our requirements.
On the other hand a larger WAL threshold would make system recovery worse and would eat up a lot of RAM.Additionally many partions could saturate VACUUM workers and cause more fragmentation in heap due to possible resizing and lack of positions to store resulting again in more RAM consumption.Generally the system won't scale up nicely for a lot of I/O data.

> c)

Under a lighter workload a PostgreSQL database would be better suited since offering ACID wouldn't affect latency constraints that are set.While with ACID we would have consistent data but higher 

### A2
> a)

Based on the CAP theorem the are as stated by Gilbert and Lynch(2002) there are three main properties in Distributed Systems.

- Consistency -> It's defined as a strict order of actions.All actions must happen as if they were one.Every read must return latest data and not stale data

- Availability -> "Every request received by a non-failing node in the system must result in a response."

- Partition tolerance -> "The network will be allowed to lose arbitrarily many messages sent from one node to another."

With those definitions the paper argues that it is impossible to implement Consistency and Availability in an Asynchronous network model since having partitions is the standard and not an option.Nodes fail,underlying network connections do not provide quarantees regarding packet delivering.
Since partions happen all the time on distributed networks then the real trade-off is between Consistency and Availability.By default Apache Cassandra DB is an AP system but can be configured to be rather Consistent than available.Engineer A and B argue on the write and read concerns and how they should be configured, modyfing them changes changes the level of conistency in our database.Engineer A's configuration make the CassandraDB fast and available but risks Consistency.While with QUORUM consistency model we a consistent Cassandra configuration with the risk of having a bottneck/wait times.

> b)

Based on Vogels(2009)-Eventually Consistent paper, a very important inequality is defined.

Defined by three parameters:

- N — number of replicas storing the data.
- W — number of replicas that must acknowledge a write before it's considered successful.
- R — number of replicas that must respond to a read before the result is returned.

The fundatmental inequality is:

> If W + R > N then we have strong consistency meaning that a read always overlaps with the most recent write.
>
>If W + R ≤ N then we have eventual consistency (the read quorum may miss the latest write)

>This works because if the write set (W replicas) and the read set (R replicas) must overlap by at least one replica, that overlapping replica is guaranteed to hold the latest write. Overlap is guaranteed from the 1st formula from above.

Based on our Replication Factor (RF=3) we can see that N=3 in our formula.Based on that in order to calculate minimum consistency levels then we need W+R = 4 which is greater than 3.

Therefore let's list possible combinations:

| W | R | Notes|
| :--- | :--- | :--- |
| 2 | 2 | Both read and writes balanced |
| 3 | 1 | Maximum write based on our replication factor |
| 1 | 3 | Maximum reads based on our replication factor |

Since we have chosen our Cassandra database for a write heavy workload we should opt to reduce the cost of writing data in our database by reducing the number of replicas that need to recognise a write.

So the minimum consistency requirements for our Cassandra database are either QUORUM/QUORUM or LOCAL_QUORUM/LOCAL_QUORUM (W=2 and R=2) or ONE/ALL(W=1 and R=3).

Even though ONE/ALL seems to be the ideal option due it low write cost, when we consider our two Data Center setup having an ONE/ALL isn't ideal since it requires all replicas to respond to a read so a single dead replica makes all reads fail and this bad for the availability requirements that we have.

Now as far as our case goes, where we have two Data Centers using plain QUORUM/QUORUM preserves the guarantee across the two Data Centers, whereas LOCAL_QUORUM/LOCAL_QUORUM can break without EACH_QUORUM on writes and deliver stale data on multi-data center setup.

So QUORUM/QUORUM proves to be the minimum consistency level for our case.

> c)

In order to evaluate Engineer A and B on the sensor ingestion part, we will evaluate their design choice on each requirement set by Section 2.2.

|Section 2.2 requirement| Value | Which engineer does it favour?|Reason
| :--- | :--- | :--- |:--- |
| Sensor write ack latency|< 50 ms| Engineer A| Writes need to be acknowledged by less replicas.|
|Sensor counter / aggregate staleness tolerance| May lag up to 30s|  Engineer A | Both engineers can deliver data in that 30s span.But that 30s time span is better utilized by Engineer's A choice since it is used to achieve eventual consistency since W=1+R=1<N=3(RF) and as per Vogels 2009 it means eventual consistency.
|Availability|Operational during any single-node failure| Tie | Both systems gurantee availability.Both Engineer A and B options survive a single-node failure.
| Throughput |40k/s normal, 120k/s storm| Engineer A| Engineer A option scales better at higher frequency data ingestions. Also given the 30s lag time, Engineer A option has more than enough time to reach eventual consistency.

The final Verdict: Engineer A solution is the better engineering decision for our problem.Engineer B's objection does not hold for this use case.Even more specifically Engineer's B argument is false regarding consistency requirments.B equates "not strongly consistent" with "violates the requirement".However as per Vogels eventual consistency is a deliberate, valid design choice when the application tolerates a bounded staleness window.In our case that window is 30s and a healty Cassandra cluster can reach eventual consistency at single-digit millisecond time, meaning it has time to reach eventual consistency before the next sensor data comes and all that while remaining inside the 30s lag window tolarated by the application.

> d)

Based on PACELC theorem (Abadi, 2012), the CAP theorem failes to capture a dimension where partions (P) are not present.The argument is that many modern datasets have severly reduced partion events and can go months without them.So the CAP theorem evolves into a consistency vs latency dillema.The new tradeoff that is introduced, is present on every request.

|System|PACELC class|Partition behaviour| Normal-operation behaviour 
| :--- | :--- | :--- | :--- |
| Cassandra | PA / EL | Favours Availability|Favours latency over consistency(but it's tunable)|
| HBase | PC / EC | Favours Consistency| Favours consistency over latency|

PACELC classification explanation

- **HBase** is classified as an EC because a region is owned by one region server.Reads and writes are routed through a single authoritative copy thus there is strong consistency by design.However coordination/region-reassignment costs latency.

- **Cassandra** is classified as an EL because it is masterless with tunable quoroms.While by default it leans towards low-latency reads.

So we can see that by eliminating partions we can evaluate a database base during normal operation.In a large monitoring system as ours latency matters a lot and Hbase sacrifies that for consistency levels that we do no need for our sensor measurent ingestion system.

### A3

> a)

For access pattern (1) we design a table with:

    CREATE TABLE sensor_readings (
      sensor_id     TEXT,
      reading_time  TIMESTAMP,
      metric_type   TEXT,
      value         FLOAT,
      unit          TEXT,
      PRIMARY KEY ((sensor_id), reading_time)
    ) WITH CLUSTERING ORDER BY (reading_time DESC);


The design for access pattern (1) is simple.Each sensor reading is stored under the appropriate partition depending on the sensor it originated.Multiple readings then are clustered based on the time they were recorded.
Additionally by ordering by reading_time in descending order we are able to parse new sensor readings first in the partion thus making it cheaper to read the top N readings without having to scan to the end.

Cassandra DB hashes sensor_id to a token and places each sensor's partition on a node (ring).That implementation helps spread data better on the distributed network and help parallelise write reducing possible bottlenecks

This way of organizing sensor readings allows us to keep each sensor's readings isolated from others,thus making it easy to filter out N readings for a specific time period.
That makes reads efficient, one query hits only one partition meaning only one and one replica set are involved no cross-node hassle

> b)

The query needed to fetch data according to the second pattern would be:

    SELECT *
    FROM sensor_readings
    WHERE reading_time > 'now − 60s'
    ALLOW FILTERING;

**ALLOW FILTERING** is specifically needed here since this query doesn't involve a partition_key Cassandra cannot route the query to specific nodes. So it has to scan every partition filtering by time at read time.

Pattern (2) cannot be served by the Cassandra database design for Pattern (1) since the first pattern is designed for a different type of query.In the first pattern we want a query to be able to return N values in a specific time space for a specific sensor, meaning that data are grouped based on the sensor_id partition they belong.This type of storage (sensor values partitioned by sensor_id and not time) would heavily increase the cost for pattern two since for a specific 60 second time period data would need to be fetched from different partitions, involving a lot of cross-node communication.

Adding extra processing time during reads would possibly be leading us to exceeding time limitations on dashboard reads (<100 ms on P95)

> c)

For pattern (2) instead of grouping sensor readings based on the sensor_id we should group them based on the time they were recorded.

So time should become the partition key in our key-space.

    CREATE TABLE sensor_readings_last_60sec (
      time_bucket   TIMESTAMP,
      sensor_id     TEXT,
      reading_time  TIMESTAMP,
      metric_type   TEXT,
      value         FLOAT,
      unit          TEXT,
      PRIMARY KEY ((time_bucket), reading_time, sensor_id)
    ) WITH CLUSTERING ORDER BY (reading_time DESC, sensor_id ASC)
    AND default_time_to_live = 3600;

The write amplification this new table introduces is, that every reading would need to be written two times.By having double the amount of writes our throughput doubles however our effective throughput halves since we introduce duplicates and not new info.Lastly since we split partitions based on time, we are more likely to have hot-partitions.At any given moment one partition would be the active one and the one receiving the whole traffic while others are sitting idle.

> d)

Having the same sensor_id partition for each sensor store days worth of data would make the partition hot for pattern (1) proposed solution.

Per Chang 2006 Bigtable:

We should "avoid row keys that hot-spot a single tablet/partition"

So based on that we can modify our table to avoid creating hot-partitions by modyfing the partition key.

    CREATE TABLE sensor_readings (
      day_bucket    TEXT,
      sensor_id     TEXT,
      reading_time  TIMESTAMP,
      metric_type   TEXT,
      value         FLOAT,
      unit          TEXT,
      PRIMARY KEY ((sensor_id, day_bucket), reading_time)
    ) WITH CLUSTERING ORDER BY (reading_time DESC);

By adding day_bucket into the primary keys we can seperate same sensor data by day and reduce partition pressure.
Each (sensor_id, day_bucket) pair hashes to a different token, so one sensor's history is spread across many partitions on different nodes over time and not one ever-growing partition.
This solution gurantees that data stay bounded as required.
Additionally the original behavior stays unchanged since sensor_id is preserved in the primary key mixture, allowing us to still query a sensor id and time frame that we want to read date from.

One thing worth mentioning is the partition time selection.The choice is deliberately daily but it could be weekly or monthly.

For 1 reading/sec(§2, page 4) from our sensor in the worst case we get 86400 rows/daily which means a 8.6MB partition in a day.Generally we want <100MB and <100k rows under Cassandra for our partitions and daily is perfectly inside those boundaries but Weekly and Montly exceed them.Weekly partition has 604800 rows added which is around 60MB.
Weekly falls under 100MB but it add over 6 times more rows.
While the cost for monthly partiotions gets larger at 2.6 million new rows at around around 260Mb each partition.

So clearly a daily partition is the best choice for spliting our sensor_id partitions but also this solution will spread our queries more, to a larger partion number.


### A4

> a)

Graphs are better suited than the other two options (Relational, Document) since they can provide index-freed adjacency.Data is connected with pointers to other data that they have a relationship with.That connection can be traversed in O(1), regardless of how much the graph grows.

The major advantage of Graphs is that the traversal cost only scales by how much of the graph we visit but not with the size of the graph.This is very important in our GridSense application since we will have millions of entries in our network and possibly the network will expand in the future.

On the contrary in our other two alternatives the size of our network heavily matters in how fast we can fetch network nodes and their relations.For starters in a realational database the query would look like this for a two-hop downstream traversal:

    SELECT *
    FROM substations s
    JOIN transformers t ON t.substation_id = s.id
    JOIN meters m ON m.transformer_id = t.id
    WHERE s.id = 'SS_001'

As we can see, we would have to use JOIN two times to merge three tables together before we can find our specific substation and from there find all connections to it.To just find one substation and its connections we would have to move information and join tables.That is fine at just to hops but when going at larger depths it becomes inefficient computationally and slow to the point that we can no longer satisfy latency requirments listed in section 2.2. (<200 ms to depth 6 across 26,000 nodes)

Regarding the document based option the same difficulty persists.Document based storage stores record with no relationships.Documents are self contained, they are accessed with an id and then with queries we can fetch info from the file records.So that means we have to embed the network inside every file.This solution is not viable an simply would not scale also if we wanted to avoid embedding network info into the file we would have to write code upstream for this implementation.

Lastly the access query in Cypher would look like this:

    // two-hop downstream
    MATCH (s:Substation {id:'SS_001'})-[:SUPPLIES|CONNECTS_TO*1..2]->(n)
    RETURN n;

    // depth 6 — change ONE number
    MATCH (s:Substation {id:'SS_001'})-[:FEEDS|SUPPLIES|CONNECTS_TO*1..6]->(n)
    RETURN n;

Complexity for the query is low and requires minimal change to go to a bigger depth than two-hops.On the other hand SQL degrades quickly with the addition of more JOINs in the query.

> b)

Definition of the property graph model:

    (GridSupplyPoint)-[:FEEDS]->(Substation)-[:SUPPLIES]->(Transformer)-[:CONNECTS_TO]->(SmartMeter)


Nodes in the Graph:

|Node label|Key property|Other properties|
| :--- | :--- | :--- |
|GridSupplyPoint|gsp_id|name, voltage_kV, region|
|Substation| substation_id | name, voltage_kV, lat, lon, commissioned_year|
|Transformer|asset_id|rating_kVA, manufacturer, model, installed|
|SmartMeter|meter_id|premise_id, tariff_class, phase|

Relationships in the Graph

|Relationship|Direction (from → to)|Properties
| :--- | :--- | :--- |
|FEEDS|GridSupplyPoint → Substation|feeder_id, voltage_kV, length_km
|SUPPLIES|Substation → Transformer|cable_id, distance_m|
|CONNECTS_TO|Transformer → SmartMeter||

Justification of properties belonging in a Relationship rather than a node

A general rule is that: a property lives on the relationship when it describes the connection, not either endpoint.

The same two devices can be reconnected by a different physical link over time, so the link's attributes belong on the edge, not baked into a node.

|Property|Relationship|Justification|
| :--- | :--- | :--- |
|voltage_kV|FEEDS|Describes the feeder line between GSP and substation, neither endpoint owns the conductor|
|length_km|FEEDS|Describes the feeder line that connects the GridSupplyPoint with a Sustation it doesn't belong to neither|
|feeder_id|FEEDS|Same as the other 2 properties of FEEDS relationship, feeder_id is unique to the line that connects the two specific nodes with specific characteristic|
|cable_id|SUPPLIES|Same as the feeder_id it is a characteristic of the cable that connects the Substation and the Transformer|
|distance_m|SUPPLIES|Same as length_km.It is a characteristic of the cable and neither of the nodes that are connected|	

> c)

Neo4j in its clustered configuration uses the Raft protocol.Writes are commited only when a majority of members acknowledge them, via the leader.If the leader fails then the system runs an election to elect a new leader.During the election event all incoming writes are rejected(Neo4j is CP chooses Consistency over Availability).

The consequence of this is that in the event of relay failure where a leader election is happening at the same time, the fault event is rejected and thus never shown upstream thus violating §2.2:"Fault alerting must remain operational during any single-node failure"

A solution to this problem, to avoid losing fault events is to initially send the fault events immediately to the dashboard to notify the engineers, even mid-election so these event do not delay significantly as system monitoring is sensitive.

Then in order to be able to store them back to the Graph database after the election the need to be buffered in strict order(2.2 "Fault event sequences must be stored in strict causal order") in an intermediate database.

For that reason we will use an AP system, a Cassandra database because it remain available when Neo4j isn't.

