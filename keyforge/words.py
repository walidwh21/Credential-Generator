"""Built-in word list used for passphrases (short, common, unambiguous)."""

_RAW = """
able acid acorn actor agile alarm album alert alley amber ample anchor angle apple apron arbor
arena argon armor aroma arrow aspen atlas attic audio aurora avid award bacon badge bagel baker
balmy bamboo banjo barn basil basin beach beacon beam bench berry bison blaze blend bloom bonus
boost brave bread breeze brick bridge brisk bronze brook brush bubble bucket cabin cable cactus
camel candle canoe canyon cargo carpet castle cedar cello chalk charm cherry chess chime cider
cinder circle citrus clever cliff clock cloud clover cobalt cocoa comet compass copper coral
cosmic cotton cougar crane crater creek crisp crown crystal cuddle cycle daisy dancer dawn delta
denim desert diamond dinner dolphin dragon drift drum eagle ebony echo eclipse ember emerald
engine envoy fabric falcon fancy feather fern ferry fiddle field finch flame flint flora flute
forest fossil fox frost gadget galaxy garden garlic gazelle gentle geyser ginger glacier glider
globe golden granite grape gravel grove guitar harbor harvest hazel heron hickory honey horizon
iceberg igloo indigo island ivory jacket jaguar jasmine jigsaw jungle kayak kernel kettle kitten
koala lagoon lantern laurel lemon lilac linen lizard lobster lotus lucky lunar magnet mango maple
marble meadow melody mesa meteor mint mirror mocha monsoon moss mountain muffin nectar needle
nickel noble nutmeg oasis ocean olive onyx opal orbit orchid otter oyster paddle palace panda
paper parrot peach pearl pebble pepper piano pine pirate planet plume pocket polar pond poppy
prairie prism puffin pumpkin puzzle quartz quill rabbit radar rain raven reef ribbon river robin
rocket saddle saffron sage sailor salmon sand sapphire scarlet shadow silver sketch solar spark
spruce squirrel stone storm summit sunset swan tango tiger timber topaz tulip tundra turtle umber
unity valley velvet violet walnut waltz whale willow window winter wolf yacht yarrow yellow zebra
zenith zephyr zigzag
"""

WORDS = tuple(sorted(set(_RAW.split())))
