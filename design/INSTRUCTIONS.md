
# goal

investigating glider performance regression and apparent ignoring of thermals in the context of presets.

using following gliders:

- GotFriends AS 33 Me 
- GotFriends Discus 2C
- Asobo DG1001e Neo


# method

the gliders have defined polars for their behavior from the performance manuals. we should source these and convert that to json.

next, we need atmospheric effect on the aircraft, turbulence, thermals, wind, ridge lift, etc. ideally these numbers should be detected separately. call this environmental data.

the environmental data can be applied to the performance data to calculated expected behavior.

this can then be compared against actual behavior.

the difference between predicted and actual should help to reveal whether there is a regression and whether this is a real bug, or just a perception.


# approach

* use python simconnect to instrument MSFS?

* write a mod to send custom telemetry to these tools?

* use a json property file for locations (i.e. Community folder)

* use keyring wrapped in first call prompt for secrets, then write. subsequent calls use stored secrets.

* raw telemetry can be json or other easy format

* analysis should be single page html SPAs on the data to show visual comparisons.

# architecture

* project should be split into two parts: telemetry and analysis.

* telemetry uses efficient techniques to gather data from the sim for analysis. a telemetry data format should be defined as we go.

* analysis uses the data efficiently to build single page html dashboards. it would be nice if this didn't require a web server, but that's negotiable.

# project

project should be versioned regularly. semver is useful.

- `README.md` provide an overview of how to use, how to contribute, etc. link to other docs.

- `CHANGELOG.md` capture features and fixes at regular milestones.

## project design

- `design/INSTRUCTIONS.md` this doc.

- `design/PLAN.md` capturing the planned work, phases, etc.

conduct work in phases. discuss the phase, then implement, then test and assess. commit work in the phase with good summary

- `design/WORKLOG.md` capturing issues and caveats encountered during plan execution

## document the project

- `doc/GUIDE.md` provide detailed doc on how to use the tools

- `doc/API.md` document the API and how to extend the analysis tools or the telemetry tools.

- `doc/TELEMETRY.md` document the telemetry format.

## working local directories

- `telemetry` stores the telemetry data files with a tools version and datetime stamp convention.

- `analysis` stores the SPAs for analysis of the data.

