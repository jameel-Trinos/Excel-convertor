export type PartyMatch = {
  /** Standard label to show in UI, e.g. "BJP Votes" */
  label: string;
  /** 0..1 confidence */
  confidence: number;
};

type PartyDefinition = {
  label: string;
  variants: string[];
  /** Optional short codes to match as substrings (e.g. BJP, AIADMK) */
  abbreviations?: string[];
};

function normalizeForMatch(input: string): string {
  return input
    .toUpperCase()
    .replace(/[\u200E\u200F\u202A-\u202E]/g, "") // strip bidi controls
    .replace(/[^A-Z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function normalizeNoSpace(input: string): string {
  return normalizeForMatch(input).replace(/\s+/g, "");
}

function reverseChars(input: string): string {
  return input.split("").reverse().join("");
}

function reverseWords(input: string): string {
  const words = input.split(/\s+/).filter(Boolean);
  return words.reverse().join(" ");
}

function reverseEachWord(input: string): string {
  const words = input.split(/\s+/).filter(Boolean);
  return words.map(reverseChars).join(" ");
}

function extractTailAfterDash(original: string): string {
  // Common Excel header: "CANDIDATE - PARTY"
  if (original.includes(" - ")) {
    const parts = original.split(" - ");
    return parts[parts.length - 1].trim();
  }
  if (original.includes("-")) {
    const parts = original.split("-");
    return parts[parts.length - 1].trim();
  }
  return original.trim();
}

function tokenSet(s: string): Set<string> {
  const tokens = normalizeForMatch(s).split(" ").filter(Boolean);
  return new Set(tokens);
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) return 0;
  let inter = 0;
  for (const t of a) if (b.has(t)) inter++;
  const union = a.size + b.size - inter;
  return union === 0 ? 0 : inter / union;
}

const PARTIES: PartyDefinition[] = [
  // IMPORTANT: Order matters! Check specific parties BEFORE generic ones
  // Major parties first (DMK, AIADMK, BJP, CONGRESS) - these are critical
  {
    label: "DMK Votes",
    abbreviations: ["DMK"],
    variants: [
      "DRAVIDA MUNNETRA KAZHAGAM",
      "MUNNETRA DRAVIDA KAZHAGAM",
      "KAZHAGAM DRAVIDA MUNNETRA",
      "MAGAHZAK ARTENNEM ADIVARD",
      "MAGAHZAK ARTENNEM ARDIVARD",
      "DMK",
      "D.M.K.",
      "D M K",
    ],
  },
  {
    label: "AIADMK Votes",
    abbreviations: ["AIADMK"],
    variants: [
      "ALL INDIA ANNA DRAVIDA MUNNETRA KAZHAGAM",
      "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM", // Without ANNA variant
      "ANNA DRAVIDA MUNNETRA KAZHAGAM",
      "ANNA DRAVIDA KAZHAGAM",
      "ALL INDIA ANNA DRAVIDA KAZHAGAM",
      "ARTENNUM ANNA MAGAHZAK AIDNI ADIVARD LLA",
      "MAGAHZAK ARTENNEM ANNA AIDNI ADIVARD",
      "MAGAHZAK ARTENNEM ANNA AIDNI ADIVARD LLA",
      "AIADMK",
      "A.I.A.D.M.K.",
      "A I A D M K",
    ],
  },
  {
    label: "BJP Votes",
    abbreviations: ["BJP"],
    variants: [
      "BHARATIYA JANATA PARTY",
      "BHARATIHA JANATA PARTY",
      "JANATA BHARATIYA PARTY",
      "JANATA PARTY BHARATIYA",
      "BHARATIYA PARTY JANATA",
      "PARTY JANATA BHARATIYA",
      "YTRAP ATANAJ AHITARAHB",
      "ATANAJ AHITARAHB",
      "JANATA PARTY",
      "BJP",
      "B.J.P.",
      "B J P",
    ],
  },
  {
    label: "CONGRESS Votes",
    abbreviations: ["CONGRESS", "INC"],
    variants: [
      "INDIAN NATIONAL CONGRESS",
      "CONGRESS",
      "NATIONAL CONGRESS",
      "SSERGNOC LANOITAN NAIDNI", // reversed OCR
      "INC",
      "I.N.C.",
      "I N C",
    ],
  },
  {
    label: "BSP Votes",
    abbreviations: ["BSP"],
    variants: [
      "BAHUJAN SAMAJ PARTY",
      "BAHUJAN PARTY SAMAJ",
      "PARTY BAHUJAN SAMAJ",
      "SAMAJ PARTY BAHUJAN",
      "SAMAJ BAHUJAN PARTY",
      "PARTY SAMAJ BAHUJAN",
      "YTRAP NAJAS UJAHAB", // reversed OCR
      "BSP",
    ],
  },
  {
    // Independent candidates - MUST come AFTER parties with "INDIA" in name
    // Use word boundary matching to avoid matching "IND" inside "INDIA"
    label: "IND Votes",
    abbreviations: ["IND", "INDEPENDENT"],
    variants: [
      "INDEPENDENT",
      "IND",
      "I.N.D.",
      "TNEDNEPEDNI", // reversed OCR
    ],
  },
  {
    // As per your latest note: treat "IHCTAK MULAADAAN LAKKAM" as NDK
    label: "NDK Votes",
    abbreviations: ["NDK"],
    variants: [
      "NDK",
      "IHCTAK MULAADAAN LAKKAM",
      "MULAADAAN LAKKAM IHCTAK",
      "LAKKAM MULAADAAN IHCTAK",
      "IHCTAK LAKKAM MULAADAAN",
    ],
  },
  {
    label: "VCK Votes",
    abbreviations: ["VCK"],
    variants: [
      "VIDUTHALAI CHIRUTHAIGAL KATCHI",
      "KATCHI VIDUTHALAI CHIRUTHAIGAL",
      "CHIRUTHAIGAL VIDUTHALAI KATCHI",
    ],
  },
  {
    label: "PMK Votes",
    abbreviations: ["PMK"],
    variants: [
      "PATTALI MAKKAL KATCHI",
      "MAKKAL PATTALI KATCHI",
      "IHCTAK MAAN KALITARAP",
    ],
  },
  {
    label: "NTK Votes",
    abbreviations: ["NTK"],
    variants: ["NAAM TAMIZHAR KATCHI", "NAAM TAMILAR KATCHI", "TAMIZHAR NAAM KATCHI"],
  },
  {
    label: "NOTA Votes",
    abbreviations: ["NOTA"],
    variants: ["NONE OF THE ABOVE", "NOTA", "EVOBA EHT FO ENON"],
  },
  {
    // India Janayaka Katchi (shows up as reversed OCR like "AKAYANAJ AYIDNI IHCTAK")
    label: "IJK Votes",
    abbreviations: ["IJK"],
    variants: [
      "INDIA JANAYAKA KATCHI",
      "INDIYA JANAYAKA KATCHI",
      "JANAYAKA KATCHI INDIA",
      "KATCHI JANAYAKA INDIA",
      "INDIA KATCHI JANAYAKA",
      // reversed OCR / character reversals seen in PDFs
      "IHCTAK AKAYANAJ AYIDNI",
      "AKAYANAJ AYIDNI IHCTAK",
      "AYIDNI AKAYANAJ IHCTAK",
      "AYIDNI IHCTAK AKAYANAJ",
      "AKAYANAJ IHCTAK AYIDNI",
      "IHCTAK AYIDNI AKAYANAJ",
    ],
  },
  {
    label: "CPI Votes",
    abbreviations: ["CPI"],
    variants: ["COMMUNIST PARTY OF INDIA", "INDIA COMMUNIST PARTY", "CPI"],
  },
  {
    label: "DMDK Votes",
    abbreviations: ["DMDK"],
    variants: ["DESIYA MURPOKKU DRAVIDA KAZHAGAM", "MURPOKKU DRAVIDA KAZHAGAM", "DMDK"],
  },
  {
    label: "AMMK Votes",
    abbreviations: ["AMMK"],
    variants: ["AMMA MAKKAL MUNNETRA KAZHAGAM", "AMMA MAKKAL KAZHAGAM", "AMMK"],
  },
];

const PARTY_INDEX = PARTIES.map((p) => {
  const variantNorms = p.variants.map((v) => normalizeForMatch(v));
  const variantNoSpace = p.variants.map((v) => normalizeNoSpace(v));
  const variantTokenSets = p.variants.map((v) => tokenSet(v));
  const abbr = (p.abbreviations ?? []).map((a) => normalizeForMatch(a));
  return { def: p, variantNorms, variantNoSpace, variantTokenSets, abbr };
});

/**
 * Best-effort match a raw Excel header to one of the configured party labels.
 *
 * High precision by default:
 * - Only returns a match if confidence >= 0.85
 * - Otherwise returns null (caller should show original header)
 */
export function matchPartyLabel(header: string): PartyMatch | null {
  const raw = header ?? "";
  const tail = extractTailAfterDash(raw);

  const candidates = new Set<string>();
  for (const s of [raw, tail]) {
    const n = normalizeForMatch(s);
    if (!n) continue;
    candidates.add(n);
    candidates.add(reverseWords(n));
    candidates.add(reverseEachWord(n));
    candidates.add(reverseChars(n));
  }

  const candidateList = Array.from(candidates);
  const candidateNoSpace = candidateList.map((c) => c.replace(/\s+/g, ""));
  const candidateTokenSets = candidateList.map((c) => tokenSet(c));

  let best: PartyMatch | null = null;

  for (const p of PARTY_INDEX) {
    let score = 0;

    // Abbreviation match (very strong signal)
    // IMPORTANT: Use word boundary matching to avoid false positives
    // e.g., "IND" should NOT match inside "INDIA" or "INDEPENDENT" when checking for IND party
    if (p.abbr.length) {
      for (const c of candidateList) {
        for (const ab of p.abbr) {
          if (!ab) continue;
          const abUpper = ab.toUpperCase();
          const cUpper = c.toUpperCase();
          
          // Exact match (highest priority)
          if (cUpper === abUpper) {
            score = Math.max(score, 1.0);
          }
          // Word boundary match - check if abbreviation appears as a whole word
          else if (abUpper === "IND" || abUpper === "INDEPENDENT") {
            // Special handling for IND: only match if it's a standalone word
            // Don't match "IND" inside "INDIA" or "INDEPENDENT" (when checking other parties)
            const wordBoundaryRegex = new RegExp(`\\b${abUpper}\\b`, 'i');
            if (wordBoundaryRegex.test(cUpper)) {
              score = Math.max(score, 0.98);
            }
          }
          // For other abbreviations, allow substring match but prioritize exact matches
          else if (cUpper.includes(abUpper)) {
            // Check if it's at word boundary or exact match
            const wordBoundaryRegex = new RegExp(`\\b${abUpper}\\b`, 'i');
            if (wordBoundaryRegex.test(cUpper)) {
              score = Math.max(score, 0.98);
            } else {
              // Substring match (lower confidence)
              score = Math.max(score, 0.85);
            }
          }
        }
      }
    }

    // Exact / no-space exact against any provided variant
    for (let i = 0; i < candidateList.length; i++) {
      const c = candidateList[i];
      const cns = candidateNoSpace[i];
      for (let j = 0; j < p.variantNorms.length; j++) {
        const v = p.variantNorms[j];
        const vns = p.variantNoSpace[j];
        if (!v) continue;
        if (c === v || cns === vns) score = Math.max(score, 1.0);
        if (c.includes(v) || v.includes(c)) score = Math.max(score, 0.92);
      }
    }

    // Token similarity against provided variants
    for (let i = 0; i < candidateTokenSets.length; i++) {
      const cset = candidateTokenSets[i];
      for (const vset of p.variantTokenSets) {
        const jac = jaccard(cset, vset);
        // Require at least 2 overlapping tokens for multiword parties to avoid false positives
        let overlap = 0;
        for (const t of cset) if (vset.has(t)) overlap++;
        if (overlap >= 2) score = Math.max(score, jac);
      }
    }

    if (!best || score > best.confidence) {
      best = { label: p.def.label, confidence: score };
    }
  }

  // High precision threshold to avoid mislabeling
  // For important parties (DMK, AIADMK, BJP, CONGRESS), require higher confidence
  const importantParties = ["DMK Votes", "AIADMK Votes", "BJP Votes", "CONGRESS Votes"];
  const isImportantParty = best && importantParties.includes(best.label);
  const minConfidence = isImportantParty ? 0.90 : 0.85;
  
  if (!best || best.confidence < minConfidence) return null;
  return best;
}


