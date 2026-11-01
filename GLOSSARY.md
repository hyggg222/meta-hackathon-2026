# Shrimp size glossary
The app measures shrimp from one phone photo next to a ruler and tells a pond farmer how fast they grow.

## Measuring
**Sample**: one photo of about 10 shrimp on a tray, with its measurements, taken on one day.
_Avoid_: scan, upload

**Tray**: the flat surface the shrimp are laid on, in a single layer.
_Avoid_: plate, board

**Reference object**: the thing of known size in the photo that gives the scale: a ruler first, a credit card as the fallback.
_Avoid_: marker, calibration card

**Scale**: pixels per millimetre, taken from the reference object.
_Avoid_: zoom

**Length**: the distance along a shrimp's curved body, in millimetres. Not the bounding box.
_Avoid_: size (size means shrimp per kg)

**Overlapped shrimp**: a shrimp whose body end touches another shrimp or the image edge. It is listed but left out of the average.
_Avoid_: bad shrimp, rejected

**Measured / left out**: the two counts on the result screen ("N measured, M left out").
_Avoid_: valid / invalid

## Sizing and money
**Size**: shrimp per kg, looked up from the length table. Fewer per kg means bigger shrimp.
_Avoid_: weight

**Length table**: the hatchery's table (CP) that maps average length to shrimp per kg. Lives in a data file.
_Avoid_: conversion formula

**Stall flag**: shows when the average length grew less than a set threshold between two samples. The farmer decides what to do.
_Avoid_: alarm, harvest alert

**Cost of a stall day**: feed kg per day times feed price, in VND, for a day without growth.
_Avoid_: loss, damage

**Demo data**: seeded samples, made for the demo and not measured from a pond. Always labelled on screen and in the video.
_Avoid_: fake data, mock data

## The old method
**Cast net sample**: the farmer's current way: catch about 1 kg with a net, weigh it, count by hand. Takes about 15 minutes and two people, hurts the shrimp, and depends on luck.
_Avoid_: net test
