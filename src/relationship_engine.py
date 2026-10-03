from typing import Dict, List, Set, Any
import pandas as pd
from src.data_model import RelationshipCandidate, Cardinality, RelationshipStatus
from src.type_detector import detect_semantic_type

# Standard exclusion list for semantics / column names that shouldn't blindly join
FALSE_POSITIVE_NAMES = {
    'city', 'state', 'country', 'postal', 'zip', 'zipcode', 'zip_code',
    'status', 'category', 'year', 'month', 'price', 'amount', 'value', 'quantity', 'cost'
}

class RelationshipDetector:
    def __init__(self):
        pass

    def _is_false_positive_target(self, col_name: str, semantic: str) -> bool:
        c = col_name.lower()
        if semantic == "Category" or semantic == "Currency" or semantic == "Percentage" or semantic == "Decimal":
            return True
        for block_word in FALSE_POSITIVE_NAMES:
            if c == block_word or (block_word in c and not ('id' in c or 'key' in c or 'code' in c)):
                return True
        return False

    def _determine_cardinality(self, src_unique: bool, tgt_unique: bool) -> Cardinality:
        if src_unique and tgt_unique:
            return Cardinality.ONE_TO_ONE
        elif not src_unique and tgt_unique:
            return Cardinality.MANY_TO_ONE
        elif src_unique and not tgt_unique:
            return Cardinality.ONE_TO_MANY
        else:
            return Cardinality.MANY_TO_MANY

    def detect(self, tables: Dict[str, pd.DataFrame]) -> List[RelationshipCandidate]:
        if len(tables) < 2:
            return []

        candidates = []
        table_names = list(tables.keys())

        # Cache stats
        col_stats = {}
        for tname, df in tables.items():
            for col in df.columns:
                series = df[col].dropna()
                total_non_null = len(series)
                if total_non_null == 0:
                    continue
                distinct = series.nunique()
                is_unique = (distinct == total_non_null)
                # Infer semantic type
                sem, _, _ = detect_semantic_type(series, col, str(series.dtype))
                col_stats[(tname, col)] = {
                    "total": total_non_null,
                    "distinct": distinct,
                    "is_unique": is_unique,
                    "semantic": sem,
                    "series": series,
                    "unique_values": set(series),
                    "value_counts": series.value_counts().to_dict()
                }

        # N x N comparisons
        for src_tname in table_names:
            for tgt_tname in table_names:
                if src_tname == tgt_tname:
                    continue

                src_df = tables[src_tname]
                tgt_df = tables[tgt_tname]

                for src_col in src_df.columns:
                    src_stat = col_stats.get((src_tname, src_col))
                    if not src_stat: continue

                    for tgt_col in tgt_df.columns:
                        tgt_stat = col_stats.get((tgt_tname, tgt_col))
                        if not tgt_stat: continue

                        # 1. Target PK check: Target must be 100% unique to be considered a PK
                        # 2. Block generic semantics
                        if self._is_false_positive_target(src_col, src_stat["semantic"]):
                            continue
                        if self._is_false_positive_target(tgt_col, tgt_stat["semantic"]):
                            continue

                        # 3. Check data overlap
                        if src_df[src_col].dtype.kind not in ['O', 'S', 'U'] and tgt_df[tgt_col].dtype.kind not in ['O', 'S', 'U']:
                            pass
                        elif src_df[src_col].dtype.kind in ['O', 'S', 'U'] and tgt_df[tgt_col].dtype.kind in ['O', 'S', 'U']:
                            pass
                        else:
                            continue

                        # Calculate coverage
                        src_set = src_stat["unique_values"]
                        tgt_set = tgt_stat["unique_values"]

                        matched = src_set.intersection(tgt_set)
                        if not matched:
                            continue

                        # matched_source_rows counts total occurrences of the matched values
                        matched_source_rows = sum(src_stat["value_counts"][v] for v in matched)
                        total_source = src_stat["total"]

                        match_coverage = (matched_source_rows / total_source) * 100.0
                        orphan_rate = 100.0 - match_coverage

                        # Threshold for candidate
                        if match_coverage <= 50.0:
                            continue

                        # If target is not unique, we require exact column name match to consider it.
                        if not tgt_stat["is_unique"] and src_col.lower() != tgt_col.lower():
                            continue

                        cardinality = self._determine_cardinality(src_stat["is_unique"], tgt_stat["is_unique"])

                        # Calculate Confidence
                        confidence = match_coverage
                        evidence = [f"Match coverage: {match_coverage:.1f}%"]

                        if src_col.lower() == tgt_col.lower():
                            confidence += 15.0
                            evidence.append("Exact column name match")

                        if tgt_stat["is_unique"]:
                            confidence += 15.0
                            evidence.append("Target key is 100% unique")

                        if orphan_rate > 0:
                            penalty = orphan_rate * 2.0
                            confidence -= penalty
                            evidence.append(f"Orphan penalty: -{penalty:.1f}%")

                        confidence = max(0.0, min(100.0, confidence))

                        candidates.append(RelationshipCandidate(
                            source_table=src_tname,
                            source_column=src_col,
                            target_table=tgt_tname,
                            target_column=tgt_col,
                            cardinality=cardinality.value,
                            source_unique=src_stat["is_unique"],
                            target_unique=tgt_stat["is_unique"],
                            match_coverage=float(match_coverage),
                            orphan_rate=float(orphan_rate),
                            confidence=float(confidence),
                            evidence=evidence,
                            status=RelationshipStatus.CANDIDATE.value
                        ))

        candidates.sort(key=lambda c: (-c.confidence, c.source_table, c.source_column, c.target_table, c.target_column))
        return candidates
