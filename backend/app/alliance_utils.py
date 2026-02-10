"""
Alliance detection and combination utilities for Tamil Nadu election data.

This module handles automatic detection and combination of party alliances
during PDF extraction.
"""

import logging
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Alliance configuration matching frontend config
ALLIANCE_CONFIG: Dict[str, List[str]] = {
    "DMK": ["KMDK", "INC", "CPI", "CPI(M)", "VCK", "IUML", "MDMK", "CONGRESS"],
    "BJP": ["IJK", "IMKMK", "PNK", "TMMK", "PMK", "TMC(M)", "AMMK"],
    "AIADMK": ["PT", "SDPI", "DMDK"],
}

# Reverse mapping: ally -> main party
ALLY_TO_MAIN_PARTY: Dict[str, str] = {}
for main_party, allies in ALLIANCE_CONFIG.items():
    for ally in allies:
        ALLY_TO_MAIN_PARTY[ally.upper()] = main_party
        # Also map common variations
        if ally == "INC":
            ALLY_TO_MAIN_PARTY["CONGRESS"] = main_party
            ALLY_TO_MAIN_PARTY["INDIAN NATIONAL CONGRESS"] = main_party
        elif ally == "CPI(M)":
            ALLY_TO_MAIN_PARTY["CPM"] = main_party
            ALLY_TO_MAIN_PARTY["CPI(M)"] = main_party


def normalize_party_name(name: str) -> str:
    """
    Normalize party name for matching.
    
    Args:
        name: Party name or abbreviation
        
    Returns:
        Normalized uppercase string
    """
    if not name:
        return ""
    # Remove common suffixes
    name = name.upper().strip()
    name = name.replace(" VOTES", "").replace(" VOTE", "")
    name = name.replace("(", "").replace(")", "")
    return name.strip()


def is_party_match(header: str, party: str) -> bool:
    """
    Check if a header matches a party name or abbreviation.
    
    Args:
        header: Column header text
        party: Party abbreviation or name
        
    Returns:
        True if header matches party
    """
    header_norm = normalize_party_name(header)
    party_norm = normalize_party_name(party)
    
    # Exact match
    if header_norm == party_norm:
        return True
    
    # Check if party abbreviation is in header
    if party_norm in header_norm:
        return True
    
    # Check common variations
    variations = {
        "DMK": ["DRAVIDA MUNNETRA KAZHAGAM", "D.M.K", "D M K"],
        "BJP": ["BHARATIYA JANATA PARTY", "B.J.P", "B J P"],
        "AIADMK": ["ALL INDIA ANNA DRAVIDA MUNNETRA KAZHAGAM", "A.I.A.D.M.K", "A I A D M K", "ANNA DMK"],
        "CONGRESS": ["INDIAN NATIONAL CONGRESS", "INC", "I.N.C", "I N C"],
        "VCK": ["VIDUTHALAI CHIRUTHAIGAL KATCHI", "V.C.K", "V C K"],
        "PMK": ["PATTALI MAKKAL KATCHI", "P.M.K", "P M K"],
        "NTK": ["NAAM TAMILAR KATCHI", "N.T.K", "N T K"],
        "CPI": ["COMMUNIST PARTY OF INDIA", "C.P.I", "C P I"],
        "CPI(M)": ["COMMUNIST PARTY OF INDIA (MARXIST)", "CPM", "C.P.M", "C P M"],
    }
    
    if party_norm in variations:
        for variant in variations[party_norm]:
            if variant in header_norm:
                return True
    
    return False


def detect_alliance_columns(headers: List[str]) -> Dict[str, Dict[str, List[int]]]:
    """
    Detect which columns belong to main parties and their alliances.
    
    Args:
        headers: List of column headers
        
    Returns:
        Dict mapping main_party -> {
            'main_cols': [indices of main party columns],
            'ally_cols': [indices of alliance columns]
        }
    """
    result: Dict[str, Dict[str, List[int]]] = {}
    
    for main_party, allies in ALLIANCE_CONFIG.items():
        main_cols: List[int] = []
        ally_cols: List[int] = []
        
        for idx, header in enumerate(headers):
            header_str = str(header).strip()
            
            # Check if this is the main party column
            if is_party_match(header_str, main_party):
                main_cols.append(idx)
            
            # Check if this is an alliance column
            for ally in allies:
                if is_party_match(header_str, ally):
                    ally_cols.append(idx)
                    break
        
        if main_cols or ally_cols:
            result[main_party] = {
                'main_cols': main_cols,
                'ally_cols': ally_cols
            }
    
    return result


def combine_alliance_headers(headers: List[str]) -> Tuple[List[str], Dict[int, int], Dict[str, Dict[str, List[int]]]]:
    """
    Combine alliance columns with main party columns.
    
    Logic:
    1. If main party AND allies both appear → combine into main party column
    2. If main party NOT available but allies appear → create main party column
    
    Args:
        headers: Original column headers
        
    Returns:
        Tuple of (combined_headers, column_mapping, alliance_info)
        column_mapping: maps old_index -> new_index
        alliance_info: alliance detection results for data combination
    """
    alliance_info = detect_alliance_columns(headers)
    
    if not alliance_info:
        # No alliances detected, return original headers
        mapping = {i: i for i in range(len(headers))}
        return headers.copy(), mapping, {}
    
    combined_headers: List[str] = []
    column_mapping: Dict[int, int] = {}
    columns_to_skip: Set[int] = set()
    
    # Track which main party columns we've added
    main_party_added: Dict[str, int] = {}
    
    # First pass: identify columns to combine
    for main_party, info in alliance_info.items():
        main_cols = info['main_cols']
        ally_cols = info['ally_cols']
        
        if main_cols:
            # Main party exists - use first main party column
            main_idx = main_cols[0]
            main_party_added[main_party] = len(combined_headers)
            combined_headers.append(headers[main_idx])
            column_mapping[main_idx] = len(combined_headers) - 1
            
            # Mark other main party columns and all ally columns to skip
            for idx in main_cols[1:]:
                columns_to_skip.add(idx)
            for idx in ally_cols:
                columns_to_skip.add(idx)
                # Map ally columns to main party column
                column_mapping[idx] = main_party_added[main_party]
        elif ally_cols:
            # Main party doesn't exist but allies do - create main party column
            main_party_name = f"{main_party} Votes"
            main_party_added[main_party] = len(combined_headers)
            combined_headers.append(main_party_name)
            
            # Map all ally columns to this new main party column
            for idx in ally_cols:
                columns_to_skip.add(idx)
                column_mapping[idx] = main_party_added[main_party]
    
    # Second pass: add non-alliance columns
    for idx, header in enumerate(headers):
        if idx not in columns_to_skip and idx not in column_mapping:
            column_mapping[idx] = len(combined_headers)
            combined_headers.append(header)
    
    logger.info(f"Combined {len(headers)} headers into {len(combined_headers)} headers (alliances merged)")
    
    return combined_headers, column_mapping, alliance_info


def combine_alliance_data_rows(
    rows: List[List[str]], 
    column_mapping: Dict[int, int],
    alliance_info: Dict[str, Dict[str, List[int]]]
) -> List[List[str]]:
    """
    Combine alliance vote data into main party columns.
    
    Args:
        rows: Original data rows (with original column count)
        column_mapping: Mapping from old column index to new column index
        alliance_info: Alliance detection results (with original column indices)
        
    Returns:
        Combined data rows with alliance votes summed into main party columns
    """
    if not rows or not column_mapping:
        return rows
    
    # Determine number of columns in output
    num_new_cols = max(column_mapping.values()) + 1 if column_mapping else len(rows[0])
    combined_rows: List[List[str]] = []
    
    for row in rows:
        new_row: List[str] = [""] * num_new_cols
        
        # First pass: copy all columns according to mapping
        for old_idx in range(len(row)):
            if old_idx in column_mapping:
                new_idx = column_mapping[old_idx]
                old_val = row[old_idx]
                if isinstance(old_val, str):
                    old_val = old_val.strip()
                
                # If this column is already filled, we need to sum (alliance case)
                if new_row[new_idx] and new_row[new_idx].strip():
                    # Sum numeric values
                    try:
                        existing = float(str(new_row[new_idx]).replace(",", "").replace(" ", "") or 0)
                        new_val = float(str(old_val).replace(",", "").replace(" ", "") or 0)
                        new_row[new_idx] = str(int(existing + new_val))
                    except (ValueError, TypeError):
                        # Non-numeric, just append
                        new_row[new_idx] = f"{new_row[new_idx]} + {old_val}"
                else:
                    new_row[new_idx] = str(old_val) if old_val else ""
        
        # Second pass: sum alliance columns into main party columns
        for main_party, info in alliance_info.items():
            main_cols = info['main_cols']
            ally_cols = info['ally_cols']
            
            if not ally_cols:
                continue
            
            # Find the new index for main party column
            main_new_idx = None
            for old_idx in main_cols:
                if old_idx in column_mapping:
                    main_new_idx = column_mapping[old_idx]
                    break
            
            # If main party doesn't exist but allies do, find the created column
            if main_new_idx is None and ally_cols:
                # The column was created during header combination
                # Find it by checking which new index the first ally maps to
                if ally_cols[0] in column_mapping:
                    main_new_idx = column_mapping[ally_cols[0]]
            
            if main_new_idx is not None:
                # Get current value in main party column
                main_val = 0
                try:
                    main_str = str(new_row[main_new_idx]).replace(",", "").replace(" ", "").strip()
                    if main_str:
                        main_val = float(main_str)
                except (ValueError, TypeError):
                    pass
                
                # Sum all alliance votes into main party column
                for ally_idx in ally_cols:
                    if ally_idx < len(row):
                        ally_val_str = str(row[ally_idx]).replace(",", "").replace(" ", "").strip()
                        try:
                            ally_val = float(ally_val_str) if ally_val_str else 0
                            main_val += ally_val
                        except (ValueError, TypeError):
                            pass
                
                # Update main party column with combined value
                new_row[main_new_idx] = str(int(main_val)) if main_val > 0 else ""
        
        combined_rows.append(new_row)
    
    return combined_rows

