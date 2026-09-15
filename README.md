Project: Exploring Common and Alternative Routes in Historical GPS Data

We will build a web application that helps users understand which paths vehicles take, how often each path is used, and how route choices change over time.

The application will handle large trajectory datasets efficiently by cleaning faulty GPS data, removing redundant points and grouping similar paths. A trajectory is a sequence of GPS positions and timestamps describing a journey.

Example

Several taxis leave a highway, take different roads through Porto, and later rejoin the highway. Their complete journeys may start and end in different places, but we want to compare the sections between their shared highway exit and entrance.

The user selects these locations and a period. The map shows the alternative paths and how many times each was taken. Moving a time slider lets the user compare route choices at different times of day.

A taxi company could use this to review unusual journeys or investigate whether certain vehicles repeatedly choose different routes from others. The data shows differences, but cannot explain their cause by itself.

How the system works

Normalise the data
Convert uploaded datasets into a common format containing journey identifiers, coordinates and timestamps. This allows the same algorithms to work with different datasets without being hardcoded for Porto or taxis.
Let the user choose a dataset
The user selects the collection to process or explore—for example, Porto or New York. Each dataset remains identifiable and separate.
Detect and handle faulty data
Check for invalid coordinates, inconsistent timestamps and implausible movement, such as a jump implying 2,000 km/h. Remove clearly faulty observations or flag uncertain sections for review. Avoid treating GPS errors as genuine alternative routes.

Simplify and store the prepared trajectories
Remove points that add little information about the path, and store the compact representation separately from the original data.

For example, several intermediate points on a straight section may be replaced by its endpoints. However, retain enough information to preserve turns, route differences and timing needed for queries.

The goal is less storage and processing work without losing information important to route comparison. The achievable reduction and any loss of accuracy must be measured.

Find relevant subtrajectories
The user selects a geographical area and an entry and exit location. The system finds journey sections that pass through the entry and then the exit.

These sections are called subtrajectories: smaller parts of complete journeys.

Group similar paths and preserve their counts
Cluster subtrajectories that follow substantially the same path. Display one representative route per group, while retaining each traversal’s identity and timestamps.

This avoids displaying hundreds of overlapping lines and allows counts to update correctly when the user changes filters. Meaningfully different routes must remain separate.

Display and compare route choices over time
The user selects a date range, such as all of May, and moves a time window between periods such as 02:00–03:00 and 15:00–16:00.

The map updates to show which paths were used and how frequently. Different colours distinguish route alternatives. Users can select a group to inspect individual journeys.

Main technical objective

Develop and evaluate algorithms that make finding, grouping and displaying subtrajectories faster and less memory-intensive, while preserving meaningful route differences and accurate counts.

We will compare the detailed and simplified data using query response time, storage size, transferred data, browser memory usage and agreement between query results.

User story

As a taxi company employee, I want to compare the paths vehicles took between shared locations during a selected period, so I can understand common route choices and investigate recurring differences without manually examining hundreds of journeys.
