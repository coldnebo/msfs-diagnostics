
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

