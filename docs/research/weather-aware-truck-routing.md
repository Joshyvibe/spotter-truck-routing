# Forecast the weather where the truck will be

Weather-aware truck routing answers one question that normal GPS skips: **what will the weather be at each point on the route at the moment this particular truck gets there?** The tool cuts the route into checkpoints and estimates the truck's arrival time (ETA) at each one. It then looks up the forecast for that place at that hour and turns each forecast into a risk level for this truck and load. Finally it adds the risk up across the route so different routes can be compared. Drivers use it to choose when to leave. Dispatchers use it to choose a route and to warn drivers. Real products split into two groups. Consumer and driver apps (Drive Weather, Highway Weather, Weather on the Way) show forecasts timed to your ETA along one route, with a departure-time slider. Fleet dashboards (Motive, Samsara, DTN, Tomorrow.io) show weather alerts on a live map of where trucks are now. Only Trimble Weather Intelligence documents comparing up to three routes with risk scored for each vehicle. No commercial product offers a "10 / 25 / 50 mile" selector. Weather APIs either make you pick the points yourself or take a free distance or time step. Most other Spotter candidates read the phrase as a choice the user makes, and a few add a default based on trip length.

## Normal GPS picks roads; weather-aware routing asks "when will I be there?"

A normal truck GPS picks a route using road rules (truck-legal roads, bridge heights, hazmat limits) plus live traffic. It does not ask whether mile 220 will be windy five hours from now, or whether that matters for this truck at this weight. Vendors sell weather routing as an extra layer on top. HERE says its trucking weather product combines weather, traffic and road-condition data with "truck-specific attributes" to give alerts along the route, alternative routes and **weather-adjusted ETAs** ([HERE](https://here.com/node/70746)).

The key idea is **forecast at ETA**, not "weather right now". Current radar tells you nothing reliable about a mountain pass you will reach in six hours. WeatherOptics' RightRoute shows the pattern clearly. It takes origin, destination and a departure time up to 7 days ahead. It then simulates the trip against hourly forecasts out to 168 hours and returns a weather-adjusted ETA and a likely delay ([WeatherOptics](https://www.weatheroptics.co/rightroute)).

This is why departure time is an input. If you leave two hours later, every ETA along the route moves two hours later too, so the truck "meets" different weather. A route that is calm at 6 AM can be dangerous at noon.

Here is an illustration (made up to explain the idea, not from a source). A driver leaves Salt Lake City at 6:00 AM heading east on I-80 with an empty 53-foot dry van. Right now it is calm near Rawlins, Wyoming. But the truck will reach the Rawlins to Laramie stretch around 1:00 PM, and the forecast for that hour shows gusts over 60 mph. A "current weather" check says go. A "forecast at ETA" check says that stretch will probably be closed to light trucks by the time you get there.

### Wind is a weight problem, which is why the brief asks for load weight

A tall box trailer works like a sail. Crosswind pushes on a big side area, and an empty trailer has little weight holding it down. Wyoming publishes the clearest official rules. WYDOT issues a "Strong Wind" notice at **40 mph gusts** and an "Extreme Blow Over Risk" warning at **60 mph or more**. It also uses partial closures to "light, high-profile vehicles", where the weight cutoff is **Gross Vehicle Weight (GVW)**, meaning the total weight of truck, trailer and cargo ([wyoroad.info](https://www.wyoroad.info/Highway/definitions.html)).

Since October 2023, WYDOT messages name a specific minimum weight. It "monitors current and forecasted wind speeds and road geometry" to work out how heavy a vehicle must be to stay safe ([WYDOT, Oct 2023](https://dot.state.wy.us/news/wydot-updates-blow-over-messaging-to-include-specific-weights)). A real example: on August 5, 2025, WY 28 at South Pass was "closed to all high-profile vehicles under 40000 GVW" on a **dry** summer road, and the cutoff was later eased to 20,000 ([County 10](https://county10.com/headsup-wy-28-south-pass-roads-closed-to-light-high-profile-vehicles-due-to-dangerous-winds-aug-5-2025/)). Enclosed trailers (box, van, reefer) are the most at risk. Empty flatbeds and tankers have little side area and are usually exempt ([WYDOT wind page](https://dot.state.wy.us/home/travel/wyoming-wind.html)). Breaking a weight-based wind closure can mean a fine of up to $750 and 30 days in jail ([WYDOT brochure](https://www.dot.state.wy.us/files/live/sites/wydot/files/shared/Public%20Affairs/brochures/blow-over%20brochure.pdf)).

There is a tension to notice. In the real world, **lighter** high-profile trucks are the ones at risk. But the assessment's load rules, as other candidates have written them down, raise the risk for **heavier** loads (for example, 35 to 44 mph wind with more than 40,000 lb is at least Severe) ([ryudantara09](https://github.com/ryudantara09/spotter-weather-truck-routing); [Vageshwar](https://github.com/Vageshwar/truck-routing-spotter-assessment)). The brief's rules are what you implement. But if you know which way real-world risk runs, you can explain your design choices better in the write-up.

### Rain and snow bring chain laws and closures

Snow and ice bring state chain laws in tiered levels. Colorado, for example, requires every truck to carry chains on I-70 between mile markers 133 and 259 from September 1 to May 31. Fines are **$500 plus surcharge** for not putting chains on when required, and **$1,000 plus surcharge** for blocking the highway ([FreightWaves](https://www.freightwaves.com/?p=561743)). National numbers show why rain matters too. About **12% of US crashes (about 745,000 a year) are weather-related**, and most of those happen on wet pavement ([FHWA](https://ops.fhwa.dot.gov/weather/roadimpact.htm)). For fatal large-truck crashes, about 8% happened in rain and about 2% in snow. Severe crosswinds were well under 1% ([FMCSA](https://www.fmcsa.dot.gov/safety/data-and-statistics/crashes-table-19-fatal-crashes-involving-large-trucks-weather-1)). So wind is mostly a regional problem: it closes roads in specific corridors more than it shows up in national death counts.

## Dispatchers plan the window; drivers make the final call

In practice, the workflow has four stages. The steps below are pieced together from safety guidance and vendor material rather than one published procedure.

**At load planning**, the dispatcher looks at the route and the ETA windows over the next few days. They flag known trouble spots, such as I-80 in Wyoming for wind or I-70 in Colorado for passes and chain laws. They also check whether the truck will be running empty on a windy stretch. Tools like RightRoute let planners test different departure times up to 7 days ahead ([WeatherOptics](https://www.weatheroptics.co/rightroute)).

**Before departure**, driver and dispatcher check National Weather Service (NWS) forecasts for the hours the truck will spend on each stretch. They also check 511 (the phone and web road-conditions service each state runs) for closures, chain controls and wind limits. Then they pick one of four options: go now, leave earlier or later, take another route, or wait. PrePass advises planning alternate routes and extra parking before winter starts ([PrePass](https://prepass.com/blog/unpredictable-weather-calls-for-predictable-trucking-resources/)).

**On the road**, drivers watch alerts and find safe parking before a closure, because truck parking fills up fast once a road shuts.

**The driver has the final say.** Federal rule 49 CFR 392.14 requires "extreme caution" in hazardous conditions, and says driving "shall be discontinued" if conditions become dangerous enough ([eCFR](https://www.ecfr.gov/on/2026-10-15/title-49/section-392.14)). Drivers are protected if they refuse to drive in unsafe conditions. But "a snow forecast or a general worry about future weather is not enough". The danger has to be real at the time ([Overdrive](https://www.overdriveonline.com/trucking-law-can-you-refuse-to-drive-in-poor-weather/)).

Hours-of-service (HOS) rules, which cap how long a driver may drive each day, give planners another reason to use forecasts. The "adverse driving conditions" exception allows up to **2 extra hours** of driving, but only for weather that was not known and could not reasonably have been known when the truck was dispatched ([FMCSA](https://www.fmcsa.dot.gov/regulations/hours-service/how-may-driver-utilize-adverse-driving-conditions-exception-or-emergency)). A forecast counts as "reasonably knowable". So if a dispatcher sends a truck into a storm that was in the forecast, the driver probably cannot use those extra hours. That gives dispatchers a strong reason to time trips around forecast windows.

## Driver apps time forecasts to your ETA; fleet tools watch where trucks are now

The products fall into two clear groups. The table sums up what the sources describe. "Not documented" means the sources did not mention the feature. It does not prove the feature is missing.

| Product | Who uses it | Forecast at ETA along route | Departure slider | Compares routes | Truck or load profile in risk |
|---|---|---|---|---|---|
| Drive Weather | Drivers, RVs, consumers | Yes | Yes | Pro tier | Not documented |
| Highway Weather (formerly Weather Route) | Drivers | Yes | Yes, plus "departure assistant" | Yes | Vehicle type (wind emphasis) |
| Weather on the Way | Consumers | Yes | Yes (3 to 7 days ahead) | PRO tier | Not documented |
| Trucker Path | Drivers | Severe-weather warnings on route | Not documented | Not documented | Not documented |
| Garmin dēzl OTR | Drivers | High-wind alerts on route | Not documented | Not documented | Height, weight, length for routing |
| Motive | Fleet managers | No, shows vehicles inside alert areas | No | No | No |
| Samsara | Fleet managers | Radar and forecast overlay on map | Not documented | No | No |
| DTN WeatherSentry | Dispatch | Route alerting for wind, snow, visibility | Not documented | Not documented | Not documented |
| Tomorrow.io FleetIQ | Dispatch and ops | Risk "for each route" | Not documented | Not documented | Not documented |
| Trimble Weather Intelligence | Dispatch and drivers | Yes, 7-day, time-aware | Not documented | **Up to 3 routes** | **Per-vehicle, incl. tipping risk** |

### Driver app flow: enter a trip, slide the departure time, read the forecast

Drive Weather is a typical example. You enter start and destination. The app works out your arrival time at points along the way and shows the forecast for each point at that time. A slider changes your departure time, and a "time tweaker" adjusts for driving faster or slower. The free tier includes animated radar. Pro adds stops, compare-alternate-routes, severe-weather alerts (including high winds), an icy-road indicator and a 7-day window instead of 2 days ([SlashGear](https://www.slashgear.com/1865598/drive-weather-app-check-along-route/)).

Highway Weather follows the same flow and adds a **departure assistant** that suggests the best start time. It also adds live highway cameras and forecasts tailored to vehicle type, for example highlighting wind for trucks ([weatherroute.io](https://www.weatherroute.io); [The Trucker](https://www.thetrucker.com/trucking-news/equipment-tech/new-app-aims-to-help-drivers-track-weather-while-on-road)).

Weather on the Way shows temperature, rain chance and amount, wind speed and gusts, visibility and sunrise or sunset at each point. Its PRO tier adds warnings, chain controls and "alternative routes to compare for best route and weather" ([Weather on the Way](https://www.weatherontheway.app/features)). None of these apps documents how it decides which route is "best".

### Fleet flow: turn on a map layer, see who is inside the storm, message them

Motive's flow is documented step by step. An admin first creates a "Weather events" alert. Then, in Fleet View, the Live tab, the user turns on the Weather Events layer. NWS alerts appear as colored shapes on the map, covering 35 event types. Clicking one opens a card showing severity, start and end times, and how many drivers and vehicles are inside it. A "Message drivers" button fills in exactly those drivers as recipients ([Motive Help Center](https://helpcenter.gomotive.com/hc/en-us/articles/36069175651997-Severe-Weather-Events-on-Live-Map)). This reacts to where trucks are now. It does not forecast along a planned route.

Trimble Weather Intelligence, an add-on to the PC\*MILER routing product built with WeatherOptics models, is the closest commercial match to the assessment. It maps 7-day forecasts onto the route and scores risk for each vehicle, including tipping risk. Its trip summaries list road names, risk levels and how long the impact lasts. Its "Alternate Route Reports" **compare up to three routes** side by side on safety, weather impact and operating cost ([Trimble](https://transportation.trimble.com/en/solutions/add-on/weather-intelligence)). Its scoring formula is not public.

The assessment's 0 to 48 hour heatmap slider has no documented commercial match. The consumer apps slide the departure time, not a forecast map. Fleet tools show overlays without documented time playback ([Samsara KB](https://kb.samsara.com/hc/en-us/articles/41311251406605-Smart-Maps-Overlays)).

## Sampling works in seven steps, and the caller usually picks the points

Across APIs and open-source projects, the method is the same seven steps.

First, a routing engine (such as OSRM, an open-source road router) returns each route as a polyline (a list of map coordinates) plus the travel time for each segment. Second, you place checkpoints along the line at a fixed distance or time step. Third, each checkpoint's ETA is the departure time plus the sum of segment times up to that point. Fourth, you fetch the forecast for that latitude and longitude at that hour. Fifth, you classify each checkpoint's risk. Sixth, you assign each checkpoint a share of the route's miles. Seventh, you add up the miles at each risk level and rank the routes.

**Most weather APIs make you choose the points.** Azure Maps takes up to **60 waypoints** per call, each with a lat, lon and ETA. It limits ETAs to 120 minutes ahead and warns that sparse points let "isolated events go undetected between waypoints". Its own example spaces points 10 minutes apart ([Microsoft Learn](https://learn.microsoft.com/zh-tw/rest/api/maps/weather/get-weather-along-route)). Spire takes the same kind of input ([Spire](https://developers.wx.spire.com/route-forecasts)).

Only two APIs expose a spacing setting. Tomorrow.io samples by **time**: the timestep can be 5, 10, 15, 30 or 60 minutes, with 10 minutes as the default. For lines it reports the maximum value by default, which is the cautious choice ([Tomorrow.io](https://llm-docs.tomorrow.io/weather-on-routes)). Xweather samples by **distance**. Its `mindist` setting defaults to 1 km, accepts values like "25 miles", and bills **each point as a separate API call** ([Xweather](https://xweather.com/docs/weather-api/actions/route)). Google has no weather-along-route endpoint. One tutorial matches each stop's ETA to "the weather interval that contains the ETA" in an hourly forecast ([AFI blog](https://blog.afi.io/blog/google-maps-weather-along-route-weather-aware-planner.md)).

Open-Meteo, the free API most candidates use, accepts many coordinates in one request, so even 10-mile sampling stays cheap ([Open-Meteo](https://open-meteo.com/en/docs/gfs-api)).

### What 10, 25 and 50 miles actually buy you

At a steady 60 mph, 10, 25 and 50 miles equal about 10, 25 and 50 minutes of driving. So 10 miles lines up with the Azure example and the Tomorrow.io default. The real question is what you might miss between checkpoints. A typical thunderstorm cell is about **12 km (7.5 miles) across and lasts about 20 minutes** ([UBC ATSC 113](https://www.eoas.ubc.ca/courses/atsc113/flying/met_concepts/04-met_concepts/04a-Tstorm_types/index.html)). Even 10-mile spacing can step over one. At 50 miles you can miss a whole cluster.

Finer spacing also stops helping once it gets smaller than the forecast model's grid. HRRR, the US high-resolution model, uses 3 km grid squares. GFS, the global model used outside North America, uses about 13 km ([Open-Meteo](https://open-meteo.com/en/docs/gfs-api)).

Time resolution is coarser than it looks. Forecasts come in hourly steps, so checkpoints 10 minutes apart often read the same forecast hour. Fine spacing adds detail across distance, not across time. The cost grows in a straight line with the number of points. For a 1,000-mile route that is about 101, 41 or 21 checkpoints at 10, 25 or 50 miles. Times three routes, that is about 303, 123 or 63 lookups (these are simple calculations).

## Worked example: five checkpoints become one route score

Take a made-up 100-mile route. The truck leaves at 6:00 AM, averages 50 mph and samples every 25 miles. The risk levels are on a 0 to 4 scale: Low = 0, Moderate = 1, High = 2, Severe = 3, No Travel = 4. In this example, the forecasts at the checkpoints' ETAs come out like this.

| Mile | ETA | Forecast hour used | Assumed result after wind, rain, snow and load rules |
|---|---|---|---|
| 0 | 6:00 | 6:00 | Low (0) |
| 25 | 6:30 | 6:00 or 7:00 (pick a rule and stick to it) | Low (0) |
| 50 | 7:00 | 7:00 | Severe (3), e.g. 40 mph wind with a load over 40,000 lb |
| 75 | 7:30 | 7:00 or 8:00 | High (2), heavy rain |
| 100 | 8:00 | 8:00 | Low (0) |

Each checkpoint takes the **worst** of its wind, rain and snow levels. Load rules can then push the wind level up but never down ([Vageshwar](https://github.com/Vageshwar/truck-routing-spotter-assessment)). If forecast data is missing, it is marked Unknown, never Low ([Ismail-ux23](https://github.com/Ismail-ux23/spotter-routing)).

Next, you turn the points into miles. Candidates use one of two methods.

With **midpoint attribution**, each checkpoint "owns" the road halfway back to the previous checkpoint and halfway forward to the next. So every mile is counted exactly once ([Vageshwar](https://github.com/Vageshwar/truck-routing-spotter-assessment)). Here the end checkpoints own 12.5 miles each and the middle ones own 25 each. The result is **25 Severe miles, 25 High miles, and 50 Low miles**. The mile-weighted average risk is (25×3 + 25×2) ÷ 100 = **1.25**.

With **segment-worst attribution**, each stretch between two checkpoints takes the worse of its two ends ([Ismail-ux23](https://github.com/Ismail-ux23/spotter-routing)). The stretches from mile 25 to 50 and from 50 to 75 both become Severe, and the stretch from 75 to 100 becomes High. The result is **50 Severe, 25 High, and 25 Low**, with an average risk of **2.0**. Same weather, twice the Severe miles. Tomorrow.io's default of reporting the maximum on lines is the same cautious idea ([Tomorrow.io](https://llm-docs.tomorrow.io/weather-on-routes)).

Now sample the same route every **50 miles** instead. You get checkpoints at 0, 50 and 100 only. The rain at mile 75 is never seen. With midpoint attribution the route shows 50 Severe miles and 0 High miles. Changing the interval changed the answer.

### Picking one of three routes

The brief ranks routes in a fixed order. First, fewest Severe miles. If that is tied, fewest High miles. If still tied, lowest average risk. If still tied, shortest time. This is called **lexicographic** ordering: you only look at the next rule to break a tie, the way a dictionary sorts words. It is not a weighted score. Several candidates add a "fewest No Travel miles" rule at the front, or drop any route with No Travel miles entirely ([ryudantara09](https://github.com/ryudantara09/spotter-weather-truck-routing); [Ismail-ux23](https://github.com/Ismail-ux23/spotter-routing)).

| Route | No Travel mi | Severe mi | High mi | Avg risk | Time |
|---|---|---|---|---|---|
| A (fastest) | 0 | 25 | 40 | 0.9 | 9h 10m |
| B | 0 | 0 | 60 | 0.8 | 10h 05m |
| C | 0 | 0 | 60 | 0.7 | 10h 40m |

Route A loses on the first rule, even though it is the fastest. B and C tie on Severe and High miles, so average risk decides it, and **C wins** even though it takes 35 minutes longer than B. The strict order puts safety ahead of time, but it also means a small difference in average risk can outweigh a large difference in time. That is worth stating in a write-up.

One detail makes the comparison fair: **use the same sampling interval for all three routes**. Otherwise a route sampled more coarsely can look safer just because fewer bad points were caught ([Vageshwar](https://github.com/Vageshwar/truck-routing-spotter-assessment)).

## What this means for the assessment

The brief text, as quoted in a candidate's README, says: "Sample weather every 10 / 25 / 50 miles, using the truck's estimated arrival time at each checkpoint" ([Vageshwar](https://github.com/Vageshwar/truck-routing-spotter-assessment)). No official Spotter copy was found, so even the exact wording comes second-hand. The research found three readings.

**Reading 1: the user picks the interval.** A control offers 10, 25 or 50 miles, often with 25 as the default. This is the most common reading among candidates. Mir-Younas, for example, says "Select checkpoint intervals of 10, 25, or 50 miles" and rejects any other value ([Mir-Younas](https://github.com/Mir-Younas/spotter-weather-routing)). ryudantara09 defaults to 25 with a UI toggle ([ryudantara09](https://github.com/ryudantara09/spotter-weather-truck-routing)), and pablomejiladev also exposes it ([pablomejiladev](https://github.com/pablomejiladev/weather-aware-truck-routing)). Upside: the trade-off between accuracy and speed is visible, and the user controls it. Downside: a novice user may not know which value to pick, and the recommendation can change when they switch.

**Reading 2: a fixed default based on trip length, which the user can override.** Vageshwar uses 10 miles for trips under 300 miles, 25 up to 1,000 miles, and 50 beyond that. The same interval is applied to all three routes, and the author notes the brief is ambiguous ([Vageshwar](https://github.com/Vageshwar/truck-routing-spotter-assessment)). Upside: sensible behavior with no input, and the number of lookups stays roughly steady. Downside: long trips get the coarsest sampling, which can miss the storm cells described above. Also, the cutoffs (300 and 1,000 miles) are invented, not taken from the brief.

**Reading 3: compute all three.** One repo describes "10/25/50 mile intervals plus both endpoints". Its README does not make clear whether it computes all three at once or lets the user choose ([Ismail-ux23](https://github.com/Ismail-ux23/spotter-routing)). Upside: you could show how stable the recommendation is ("Route C wins at every interval"). Downside: about 1.6 times the lookups of the 10-mile run alone (163 versus 101 checkpoints per 1,000-mile route, before removing points the runs share), and a harder question about which result is the "official" one.

What real products do helps only partly. No commercial product or API offers a 10/25/50 selector. The closest is Tomorrow.io's fixed list of time steps (5 to 60 minutes, default 10). Xweather takes any distance you choose. The consumer apps hide their spacing completely ([Tomorrow.io](https://llm-docs.tomorrow.io/weather-on-routes); [Xweather](https://xweather.com/docs/weather-api/actions/route); [SlashGear](https://www.slashgear.com/1865598/drive-weather-app-check-along-route/)). Trimble, the one product that ranks routes, compares up to three, which matches the brief's "3 routes", but it does not publish how it scores them.

For the recommendation, the open choices are these. Should "No Travel" miles come before Severe miles, or should those routes be excluded altogether? Should risk be assigned to miles by midpoint or by segment-worst? And should each ETA use the nearest forecast hour or the hour that contains it? The worked example shows that each choice can change the numbers. That makes them worth stating openly, whichever way they go.

## Conclusion

Seen from the outside, the hard part of weather-aware routing looks like the weather data. The research points elsewhere. The forecast lookup is a commodity, since free APIs like Open-Meteo take many points in one request. The judgment sits in three quiet choices: how far apart the checkpoints are, how a point's risk spreads into miles, and how strictly the ranking puts safety ahead of time. In the 100-mile example, two attribution methods turned the same five forecasts into 25 or 50 Severe miles. Moving from 25-mile to 50-mile sampling erased a High stretch completely.

That shifts what a strong submission shows. Commercial products mostly hide these choices, and the one fleet tool that ranks routes keeps its formula private. So a solution that states its interval reading, applies it the same way to all three routes, and shows why the winner won (for example, "C beats B on average risk after tying on Severe and High miles") offers more transparency than the products it imitates. The same goes for flagging where the brief's load rules differ from Wyoming's real-world logic that lighter trucks are more at risk.
