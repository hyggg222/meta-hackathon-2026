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

**Overlapped shrimp**: a shrimp whose body end touches another shrimp or the image edge. It is listed, and by default left out of the average; the farmer can choose to count it.
_Avoid_: bad shrimp, rejected

**Chosen shrimp**: the shrimp that count in the average of one sample. The photo starts with every shrimp that is not overlapped chosen; the farmer taps a shrimp on the photo to add or remove it, and the code recomputes length and size from exactly those shrimp.
_Avoid_: selected, valid shrimp

**Measured / left out**: the two counts on the result screen ("N measured, M left out"): measured is the number of chosen shrimp.
_Avoid_: valid / invalid

## Sizing and money
**Size**: shrimp per kg, looked up in the length table at the sample's average length. Fewer per kg means bigger shrimp.
_Avoid_: weight

**Length table**: rows of average length (mm) and shrimp per kg, read from a replaceable data file, with straight-line interpolation between rows. It covers 60 to 140 mm; outside that range there is no size. Until the hatchery's (CP) table arrives it is a temporary public table, labelled as such on screen.
_Avoid_: conversion formula

**Stall flag**: shows when the average length grew less than the threshold (0.33 mm per day) between the last two samples. It needs both samples to have enough measured shrimp (5 by default) and at least one day between them; otherwise it says it cannot tell. The farmer decides what to do. On screen it is worded as a hint ("Growth looks slow"), never as an order or an alarm. When the samples are too noisy to tell growth from the threshold (a handful of shrimp varies by a few mm by chance) it says "unclear" and how many shrimp or days would settle it.
_Avoid_: alarm, harvest alert, cull, sell

**Harvest size flag**: shows when the size is at or below the harvest size (50 per kg by default). Information only, never advice to harvest.
_Avoid_: harvest alert, harvest advice

**Cost of a stall day**: feed kg per day times feed price, in VND, for a day without growth. It uses the latest feed entry on or before the latest sample's day.
_Avoid_: loss, damage

**Demo data**: seeded samples, made for the demo and not measured from a pond. Always labelled on screen and in the video.
_Avoid_: fake data, mock data

## The old method
**Cast net sample**: the farmer's current way: catch about 1 kg with a net, weigh it, count by hand. Takes about 15 minutes and two people, hurts the shrimp, and depends on luck.
_Avoid_: net test

## The chat
**Bot**: the Messenger account the farmer sends the tray photo to. It replies with the measured photo and a few lines, and saves the sample only after the farmer says yes.
_Avoid_: assistant, agent (the bot never decides for the farmer)

**Reply photo**: the tray photo sent back by the bot, with each counted shrimp outlined, its body line and number drawn on it, and shrimp that do not count marked as left out.
_Avoid_: overlay (that was the web page's word)

**Minimum length**: shrimp shorter than this (50 mm by default, editable in Setup) are treated as fragments and left out of the average.
_Avoid_: noise filter

## Reading the numbers
**Merged shrimp**: a mask that joins two or more overlapping shrimp, so its length is not one shrimp's. It is left out of the default choice; the farmer can still add it by number.
_Avoid_: duplicate, error shrimp

**Crowded tray**: a photo where at least half of the shrimp (8 or more masks) are left out by default because they touch or merge. The text asks the farmer to lay the shrimp apart and shoot again.
_Avoid_: bad photo

**Growth trend**: the slope of a weighted line through the average lengths of the last up to four samples. It is steadier than the growth between two samples, because a handful of shrimp moves the average by a few millimetres by chance.
_Avoid_: speed

**Size class**: a price step of shrimp per kg (20, 30, 40 ... 100). The price per kg falls by class and falls fastest at the large end.
_Avoid_: grade, bracket

**Feed break-even growth**: the growth in mm a day above which the weight gained in a day is worth at least the feed of that day. It counts feed only, not power, labour, risk or price steps, and is an estimate.
_Avoid_: profit line
