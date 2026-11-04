# Smash Bros. study path

Yes, this series discusses Smash's mechanics and design in substantial detail. The inherited episode metadata names Smash in 135 of the 261 non-compilation records. That is a discovery count, not 135 dedicated mechanics lessons or independent confirmations. Some episodes use it as an example, show footage, or discuss production.

The sequence below follows the original episode order. The first mechanics explanations have been read in their retained notes or transcripts; the later entries are linked candidates identified from existing titles and metadata. The source is English on-screen subtitles captured through third-party OCR. Exact wording and demonstrations still need audiovisual checking before implementation-sensitive claims are treated as verified.

## Start with the original concept

[Super Smash Bros., episode 27](https://www.youtube.com/watch?v=i3IOWaVDbx0), explains the genre problem behind the design. Sakurai wanted more interplay and improvisation rather than an outcome largely decided by a long input sequence after the first hit. Accumulated damage changes reactions to later hits, while ring-outs decide a loss regardless of damage. Stick direction plus a button, and the timed flick for stronger input, reduced command complexity.

The Dragon King prototype already had the core movement and combat rules before special moves, dodges, or items. Nintendo characters were added later to address first impressions of an unfamiliar roster. Configurable player counts and item rules served different kinds of play. For a new platform fighter, ask which interaction problem its launch rules and input model solve. Do not infer that licensed characters or a copy of Smash's controls are necessary.

Read the [episode note](../episodes/notes/027-super-smash-bros.md) and [retained transcript](../episodes/transcripts/027-super-smash-bros.md). This is the earliest dedicated Smash concept episode, not the first appearance of Smash footage anywhere in the channel.

## Understand an attack before adding effects

[Breaking Down Attack Animations, episode 36](https://www.youtube.com/watch?v=LewXWM7HDd8), connects standby, lead-in, attack, and follow-through with response, readable contact poses, and recovery/cancel windows. The note distinguishes Melee-era behavior from later cancel-frame treatment. It is a starting point for an attack specification, not a claim about every competitive cancel system or input buffer.

Read the [note](../episodes/notes/036-breaking-down-attack-animations.md), then inspect the cited demonstration. Specify which frames register input, deal damage, expose recovery, and allow another action. Actual values should be tuned for the game, not invented as Sakurai's numbers.

## Separate sequel ambitions from the core mechanic

[Super Smash Bros. Melee, episode 40](https://www.youtube.com/watch?v=vLRRNsAVl-8), is a sequel and hardware case. The concept was to upgrade the original dramatically across content and presentation. GameCube headroom enabled visual expansion and recorded music; trophies broadened representation without making every character playable.

Read the [note](../episodes/notes/040-super-smash-bros-melee.md). This is useful for scope and differentiation, not a tutorial on wavedashing or a complete account of Melee's competitive physics. Historical overwork is not a recommendation for a small team to reproduce that schedule.

## Make contact feel strong without breaking collision

[Eight Hit Stop Techniques, episode 47](https://www.youtube.com/watch?v=tycbMSjDDLg), uses Smash Ultimate to explain model shake separately from collision, grounded versus airborne shake, strength/multiplier scaling, damage-pose blending, optional attacker animation creep, multiplayer adjustments, and camera-distance compensation.

The approximately four-frame value is for a **damage-pose blend**, not a universal hitstop duration. Grounded horizontal shake addresses floor clipping in a 3D character presentation. Sword creep is optional per attack. These conditions matter even if the new game has a similar camera and combat.

Read the [note](../episodes/notes/047-eight-hit-stop-techniques.md) and [retained transcript](../episodes/transcripts/047-eight-hit-stop-techniques.md). The fork's evidence pilot links those details to stable source locators; it does not claim the original visuals have been reverified.

## Continue through stage and game-concept candidates

The next dedicated Smash records in order are [An Up-Close Look at Smash Bros. Stages, episode 99](https://www.youtube.com/watch?v=lvYN7JciOdk), [Super Smash Bros. Brawl, episode 108](https://www.youtube.com/watch?v=dXpFTHtlmCo), [The Team Behind Super Smash Bros. Brawl, episode 132](https://www.youtube.com/watch?v=MammcQ3XkpY), and [Super Smash Bros. for 3DS / Wii U, episode 135](https://www.youtube.com/watch?v=DeLrIXCOUw0). Treat stage showcase material and team history differently from a rule specification. These are navigation targets, not newly extracted conclusions.

## Study knockback as a designed payoff

[Knockback in Super Smash Bros., episode 145](https://www.youtube.com/watch?v=HVktK4a9Yfo), is the most directly relevant parameter discussion for a platform fighter. Attack damage and accumulated target damage affect launch. Attack direction and an optional travel-direction modifier, target weight/fall velocity, a multiplier, a guaranteed minimum with scaling, and fixed knockback allow move-specific behavior.

Mario's Super Jump Punch illustrates fixed knockback for successive hits and ordinary knockback on the finisher, so changing target damage does not prevent the sequence from connecting. The episode explains parameter roles, not a complete executable formula or every interaction. It explicitly says more parameters exist.

Read the [note](../episodes/notes/145-knockback-in-super-smash-bros.md) and [retained transcript](../episodes/transcripts/145-knockback-in-super-smash-bros.md). The pilot marks these as source examples for a launch-centered game. A health-depletion-only combat game may not need this structure.

## Finish with character identity, balance, and testing candidates

Continue with [Super Smash Bros. Ultimate, episode 160](https://www.youtube.com/watch?v=RDrNWAHaKfI), then [Average and Mediocre Are the Same Thing, episode 218](https://www.youtube.com/watch?v=KW4x-_Y8BmM), [Play Testing Keeps Going, episode 220](https://www.youtube.com/watch?v=TayNJ4603Hc), [Computer-Controlled Players, episode 221](https://www.youtube.com/watch?v=uleauI0IwZM), and [Always Keep Attack Collision in Mind, episode 225](https://www.youtube.com/watch?v=rwwF_4blK-o).

Later candidates are [Smash Bros. DOJO!!, episode 245](https://www.youtube.com/watch?v=v4BG0wnc72s), [Amplify Both Strengths and Weaknesses, episode 247](https://www.youtube.com/watch?v=fc-hOvTBTCc), and [Elementary School Play Testers, episode 248](https://www.youtube.com/watch?v=aACUZ769djE). The inherited notes identify themes of character distinctness, testing, human-like CPU limits, matching collision to animation, and communicating the game to players. Verify each source before turning those themes into new parameter rules.

## Apply the material through a game brief and an experiment

Use `examples/platform-fighter.json` as a sample brief, not a declaration of this project's design. Choose a mechanic-specific query, read its source conditions, and compare one change at a time. The `experiments/` templates describe proposed measurements and explicitly contain no playtest results.

For source questions, preserve the distinction between what the video states, what the existing guide synthesizes, and what our prototype tests. Do not fill gaps such as exact hitstop frames, coyote time, or a complete knockback formula by attributing guessed values to Sakurai.
