# Lab Simulator: design

The 20 techniques, grouped in four wings around the board, and the minigames played at each bench.
Every step scores 0-100; the average of the steps gives 1, 2 or 3 stars (40, 65, 85 points).
Each technique has its own procedurally composed tune.

## DNA

### 1. Polymerase chain reaction

Copies one chosen stretch of DNA millions of times, so that it can be seen on a gel, sequenced or cloned.

*Music: Thermocycler Funk* (dor, 108 bpm, epiano lead)

1. **Raid the -20°C freezer.** Find the 7 PCR reagents in the freezer box before your fingers freeze. Hover to read a label, click to take it. Wrong tubes cost 3 seconds.
2. **Make the master mix.** Type the total volume of each reagent for the whole master mix, then hand it out: 24 µL into every PCR tube. Pipettes are never perfect, so plan for it.
3. **Program the thermocycler.** Set the temperatures, the extension time and the number of cycles for this primer pair and product, then press Run.
4. **Load the gel.** Move the pipette tip over the flashing well and hold the mouse button to push the sample in. Your hand shakes more when you move fast or hold too long. Hold Space to rest your elbow on the bench: steadier, but only for a few seconds at a time. Sample outside the well is lost.
5. **Run the gel.** Current is on: the purple loading dye runs towards the red (+) electrode. Click or press Space to stop when the dye front is about three quarters down the gel, before it runs off.

### 2. Agarose gel electrophoresis

Sorts DNA fragments by size in an electric field, so you can see whether a PCR or digest gave the band you expected.

*Music: Agarose Waltz* (maj, 138 bpm, bell lead)

1. **Choose the gel.** Pick the agarose percentage for the fragments shown and answer questions on how DNA runs in a gel.
2. **Melt the agarose.** Agarose only dissolves near boiling. Stop the microwave when the solution turns clear, before it foams up and boils over. Two flasks.
3. **Pour the gel.** Click the comb to drop it into the tray, then pop every air bubble with a tip before the gel sets. Bubbles near the wells distort the lanes.
4. **Read the gel.** Estimate each band size by comparing it with the ladder.

### 3. Nucleic acid extraction (plasmid miniprep)

Breaks open cells and purifies their DNA or RNA away from proteins, lipids and salts, ready for enzymes and sequencing.

*Music: Spin Column Shuffle* (blues, 116 bpm, organ lead)

1. **Miniprep protocol.** Put the miniprep steps in order. Each step explains what it does once placed.
2. **Lyse and neutralise.** Hold the mouse button and move up and down to turn the tube over and back. Invert 6 times after adding the lysis buffer (the lysate turns blue), then press 'Add neutralisation buffer' and invert 6 times more. Keep the speed in the green band: rough mixing shears the bacterial chromosome. Lysis must not run past 5 minutes.
3. **Balance the centrifuge.** Place all the tubes in the rotor so that it is balanced (the centre of mass must stay in the middle), then press Spin. Click a slot to add or remove a tube.
4. **Read the NanoDrop.** Judge the purity and concentration of your prep from the spectrophotometer readings.

### 4. Molecular cloning (restriction digest and ligation)

Cuts a gene out with restriction enzymes and pastes it into a plasmid vector, so bacteria can copy it or cells can express it.

*Music: Restriction Rondo* (harm, 120 bpm, harpsi lead)

1. **Find the restriction sites.** Click every EcoRI site (GAATTC) and every BamHI site (GGATCC) in the plasmid sequence. Clicking elsewhere costs points.
2. **Plan the cloning.** Choose the enzymes for directional cloning, then answer two questions on ligation.
3. **Sticky ends.** Read where each enzyme cuts (^) and connect it to the end it leaves. The red strand is 5' to 3'.
4. **Set up the ligation.** Work out how much insert to add for the molar ratio you want.

### 5. Bacterial transformation

Puts a plasmid into bacteria, which then copy it every time they divide. The antibiotic on the plate keeps only the cells that took it up.

*Music: Heat Shock Polka* (maj, 144 bpm, whistle lead)

1. **Heat shock.** The clock runs fast. Lift the tube out of the 42°C bath at 45 seconds (the green zone): click or press Space.
2. **Spread the plate.** Hold the mouse button and sweep the glass spreader across the agar until the whole plate is covered. Fast jabs tear the agar.
3. **Blue / white screening.** Pick every white colony with a toothpick: they most likely carry a plasmid with your insert. Blue colonies have an empty vector. Tiny satellite colonies around a big one have no plasmid at all.

## Genes & genomes

### 6. Sanger sequencing

Reads the order of bases in one DNA fragment, up to about 1000 bases, by stopping copies at each base with coloured terminators.

*Music: Chromatogram Rag* (maj, 138 bpm, epiano lead)

1. **Read the trace.** Peaks scroll to the left. Type the base of each peak before it crosses the red line: A green, C blue, G black, T red. Two equal peaks on top of each other: type N. Then compare your read with the wild-type reference and click the mutation.
2. **Judge the trace.** Look at each piece of chromatogram and say what it tells you.
3. **Reverse complement.** To read the other strand you need the reverse complement: swap A<→T and C<→G, then read from the other end. Type it 5' to 3'.

### 7. Quantitative real-time PCR

Measures how much of a DNA or cDNA sequence is in a sample by watching fluorescence rise during PCR, cycle by cycle.

*Music: Threshold Trance* (min, 126 bpm, synth lead)

1. **Set the threshold.** Move the mouse to place the threshold line, then click. Put it above the baseline noise and in the straight (exponential) part of every curve. Then check the wells: click the one with a problem, or 'All wells fine'.
2. **Read the curves.** Amplification and melt curves: what do they say?
3. **Fold change.** Work out relative expression with the 2^-ddCt method. Type the number and press Enter.

### 8. Next-generation sequencing

Reads hundreds of millions of short DNA fragments at once, to sequence whole genomes or count every RNA in a sample (RNA-seq).

*Music: Flow Cell Flicker* (dor, 172 bpm, square lead)

1. **Sequencing by synthesis.** Each cycle adds one fluorescent base to every cluster, then the camera takes a picture. Call the colour of the circled cluster: A green, C blue, G yellow, T red. Expert: the second cluster is read on a two-colour instrument.
2. **Align the reads.** Drag each read left or right until it matches the reference (or select it and use the arrow keys). Then click the reference base where the reads show a real variant.
3. **Volcano plot.** Each dot is one gene from an RNA-seq comparison. Find the gene asked for.

### 9. CRISPR-Cas9 genome editing

A guide RNA leads the Cas9 enzyme to one place in the genome, where it cuts both DNA strands. Repair errors then disrupt the gene.

*Music: Guide RNA Groove* (mix, 106 bpm, brass lead)

1. **Find the PAMs.** Cas9 can only cut next to a PAM: the sequence NGG (any base, then two Gs). Click every NGG on the top strand (a CCN is a bonus: an NGG on the bottom strand). Then pick the PAM you will use for your guide.
2. **Choose a guide.** Pick the guide RNA that will give a clean knockout.
3. **Where does Cas9 cut?.** The guide RNA leads Cas9 to the 20 bases next to the PAM. Cas9 cuts both strands 3 bases upstream of the PAM. Click the gap where it cuts.
4. **Did it work?.** Genotyping results from injected embryos and their offspring. What do they show?

### 10. Whole-mount in situ hybridisation

Shows where in the embryo a gene is switched on, by letting a labelled RNA probe pair with its mRNA, then using an antibody-linked enzyme to leave a purple stain where the probe sits.

*Music: Sixty-Five Degrees* (harm, 80 bpm, whistle lead)

1. **The protocol.** Click the steps of a whole-mount in situ in the right order.
2. **Proteinase K.** Proteinase K opens the tissue for the probe. Click (or Space) to stop the digest at the right time.
3. **Watch the colour.** The purple stain develops over hours. Top: antisense probe (the real pattern). Bottom: sense probe (should stay clean). Click or press Space when the pattern is strong and the control still pale.
4. **Controls.** Antisense, sense and why the protocol works.

## Proteins

### 11. SDS polyacrylamide gel electrophoresis

Separates proteins by size. SDS unfolds them and coats them with negative charge, so in an electric field they move through the gel at a speed set by their length.

*Music: Laemmli March* (maj, 112 bpm, brass lead)

1. **Denature the samples.** Samples sit at 95°C in Laemmli buffer. Stop at about 5 minutes: long enough to unfold the proteins, not so long that the tubes dry out and fragile proteins clump.
2. **Predict the bands.** Click the proteins in the order their bands appear, from the top of the gel (largest) to the bottom (smallest).
3. **Load the gel.** Bring the pipette tip into the glowing well and hold the mouse button to release the sample. Move slowly: fast moves make your hand shake. Stay inside the well; below it you pierce the gel. Release the button before moving to the next well.
4. **Run the gel.** Proteins run from the black (-) electrode to the red (+). Stop when the blue dye front is near the bottom of the gel, before it runs out.

### 12. Western blot (immunoblot)

Proteins separated by SDS-PAGE are moved onto a membrane and detected with antibodies, to show whether a particular protein is there and roughly how much.

*Music: Transfer Sandwich Blues* (blues, 84 bpm, organ lead)

1. **Build the transfer sandwich.** Stack the layers from the black (-) side up to the red (+) side. Proteins carry SDS and move towards +.
2. **Roll out the bubbles.** Air bubbles between gel and membrane block the transfer. Hold the mouse button to press the roller and roll up or down to push every bubble off the edge. Roll steadily: jerking the roller makes the membrane slide on the gel.
3. **Antibody steps.** Put the detection steps in order.
4. **Expose the blot.** The imager collects light from the bands. Stop when the bands are clear but before the brightest one saturates (turns red).

### 13. Sandwich enzyme-linked immunosorbent assay

Measures how much of a protein is in a liquid. Two antibodies trap it in a plastic well and an enzyme makes a colour whose strength follows the amount of protein.

*Music: Plate Reader Waltz* (maj, 132 bpm, bell lead)

1. **Build the sandwich.** Click the steps in the order you add them to the well (the washes between steps are left out). The well on the right shows what you have built.
2. **Serial dilution.** Make the dilution series asked for, from well 1 to well 8. Click a well to draw up liquid, click another to dispense, and press Mix after every transfer. Set the pipette volume with + / – or the mouse wheel.
3. **Read the standard curve.** Click the right answer (or press 1-4).
4. **Stop the colour.** The plate turns blue as HRP works. Add the stop solution when the standards show a clear gradient, before the top ones max out and the blank turns blue.

### 14. His-tag affinity chromatography

Pulls one protein out of a cell extract. A tag of six histidines on the protein binds nickel ions on a column; everything else washes through, then imidazole releases the protein.

*Music: Column Calypso* (mix, 118 bpm, marimba lead)

1. **Purification protocol.** Click the steps in the order you would do them.
2. **Collect the fractions.** The UV trace shows protein leaving the column. Hold the mouse button (or Space) to send the flow into your fraction tubes; release it to send it to waste. When the wash has brought the trace back to the baseline, press Elute (or E) to switch to 250 mM imidazole, then keep your His-tagged protein, not the rest.
3. **Seminar on the column.** Click the right answer (or press 1-4).

### 15. Immunofluorescence and fluorescence microscopy

Shows where a protein sits inside cells. Antibodies carrying fluorescent dyes bind the protein, and a microscope lights each dye with its own colour of light.

*Music: Confocal Nocturne* (lyd, 72 bpm, epiano lead)

1. **Dyes and lasers.** Match each dye to the laser that excites it and the colour it gives off.
2. **Focus the microscope.** Turn the focus until the cells are sharp, then press Capture (or Space). Drag the outer coarse knob, use the mouse wheel or the inner fine knob for fine focus. The sample drifts: keep it sharp, and do not linger, because the lamp bleaches the dye while you look.
3. **Capture before it fades.** The exposure rises step by step while the lamp bleaches the dye. Capture when the image is brightest, before the fading wins.
4. **Antibodies and controls.** Click the right answer (or press 1-4).

## Cells & embryos

### 16. Cell culture and aseptic technique

Growing cells outside the body, in flasks of medium at 37 °C, without letting bacteria or fungi in.

*Music: Laminar Flow Lullaby* (lyd, 84 bpm, vibes lead)

1. **Keep it sterile.** Microbes drift into the hood from the room. Click them to spray 70 % ethanol before they reach the open flask. Don't put your hands on the empty front grille: blocking it breaks the air curtain. Spraying at nothing disturbs the airflow too.
2. **Time to split?.** Look at the flask in the microscope and decide what to do.
3. **Trypsin.** Trypsin is loosening the cells. Click (or press Space) when most cells float free, before they get damaged.
4. **Split the cells.** Type the answer and press Enter. Use the keypad or the keyboard.

### 17. Cell counting with a haemocytometer

Counting cells in a chamber of known volume under the microscope, to know how many cells you have and how many are alive.

*Music: Grid Counting Gavotte* (maj, 116 bpm, harpsi lead)

1. **Count the live cells.** Click every live (bright, unstained) cell that counts in the large square. Blue cells took up trypan blue: they are dead, skip them. Count cells touching the top or left line, not the bottom or right line.
2. **Cells per mL.** Turn your counts into a concentration. Type the answer and press Enter.

### 18. Transfection by lipofection

Packing plasmid DNA into positively charged lipid particles so that cultured cells take it up and express the gene.

*Music: Lipoplex Disco* (dor, 120 bpm, synth lead)

1. **Form the complexes.** DNA and lipid are coming together. Stop the incubation (click or Space) at about 15 minutes, as the kit asks; the green band shows the time that still works.
2. **Deliver the lipoplexes.** Move the pipette along the dish and click to let a drop of lipoplexes fall onto the cells. It must land on top of a cell (the nucleus area); each cell needs one. The cell takes it up by endocytosis and starts making GFP. You have only a few spare drops. (A game shortcut: in a real dish the drops spread through the medium and nobody aims at single cells.)
3. **How well did it work?.** Judge the result under the fluorescence microscope.

### 19. Flow cytometry and fluorescence-activated cell sorting

Measuring the light scatter and fluorescence of thousands of single cells per second, and sorting the ones you want.

*Music: Droplet Drum and Bass* (min, 168 bpm, square lead)

1. **Sort the stream.** Cells fall one by one through the lasers. Press LEFT for GFP-only (green) cells and RIGHT for mCherry-only (red) cells, before they reach the plates. Do nothing for cells that are both or neither: they go to waste. Dim cells still count. A droplet holding two cells must go to waste too.
2. **Draw the gate.** Drag a box around the main population of intact cells on the forward (FSC) versus side scatter (SSC) plot. Leave out the debris, dead cells and clumps. Then press Confirm.
3. **Read the dot plot.** Read the GFP versus mCherry plots.

### 20. Zebrafish embryo microinjection

Injecting a nanolitre of mRNA, DNA, morpholino or Cas9 into freshly fertilised zebrafish eggs with a fine glass needle.

*Music: Yolk Sac Serenade* (pent, 84 bpm, whistle lead)

1. **Calibrate the needle.** Hold the mouse button (or Space) to push injection mix into a drop of mineral oil. Release when the bolus has the right diameter on the micrometer scale. The volume of a sphere is πd³/6.
2. **Inject the embryos.** Put the needle tip into the yolk or the cell of each embryo and hold the button to inject. Release when the pink bolus fills the dashed ring. Inject them all at the one-cell stage, before they divide. Your needle setting from the calibration decides how fast the bolus grows.
3. **Injection know-how.** Three questions from the injection room.

## The board

28 benches in a loop: the 20 techniques in wing order, with Start, two Lab notebook, two Seminar,
one Coffee, one Contamination and one Conference bench between them. See README.md for the rules.
