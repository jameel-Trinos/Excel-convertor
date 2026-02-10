/**
 * Tamil Nadu Election Alliance Configuration
 *
 * Keys: main party abbreviations
 * Values: alliance party abbreviations
 *
 * These abbreviations are matched against column headers using
 * matchPartyLabel() from partyHeaderMapper.ts
 */

export const ALLIANCE_CONFIG: Record<string, { color: string; allies: string[] }> = {
  DMK: {
    color: "#e53e3e", // red
    allies: ["KMDK", "INC", "CPI", "CPI(M)", "VCK", "IUML", "MDMK"],
  },
  BJP: {
    color: "#ed8936", // orange
    allies: ["IJK", "IMKMK", "PNK", "TMMK", "PMK", "TMC(M)", "AMMK"],
  },
  AIADMK: {
    color: "#38a169", // green
    allies: ["PT", "SDPI", "DMDK"],
  },
};

/** All main party keys */
export const MAIN_PARTIES = Object.keys(ALLIANCE_CONFIG) as Array<keyof typeof ALLIANCE_CONFIG>;
