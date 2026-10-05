"""Copy KG source tables to canonical data paths, preserving file hashes."""
import hashlib, json, logging, os, shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source_paths=['Source/ROCS/data/combined_sst_proxies_separate_columns.csv','Source/ROCS/data/combined_foraminifera_geochem.tsv','Source/ROCS/data/geob25202_clean_proxies.tsv','Source/ROCS/data/combined_xrf_geochemistry_not_normalized.csv','Source/ROCS/data/combined_xrf_geochemistry_curated.csv','Source/ROCS/results/microbial/damage/damage-classification-depositional/sample-baselines.tsv']
def main():
    out=root/'data/kg_feedstock';out.mkdir(parents=True,exist_ok=True)
    log=root/'logs'/os.environ.get('NG_LOG_SCOPE','')/'kg_feedstock_import.log';log.parent.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=log,level=logging.INFO)
    records=[]
    for relative in source_paths:
        source=root/relative;target=out/source.name
        source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=source_hash:
            raise SystemExit('Canonical copy differs; inspect before replacement: '+str(target))
        if not target.exists():shutil.copy2(source,target)
        records.append({'source':relative,'canonical':str(target.relative_to(root)),'sha256':source_hash})
        logging.info('Verified %s',relative)
    (root/'data/provenance/kg_feedstock_import.json').write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':main()
