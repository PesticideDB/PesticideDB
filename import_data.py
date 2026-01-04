import pandas as pd
import os
import django
import sys

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PepDatabase.settings')
django.setup()

from base.models import Pesticide, NoEvidencePesticide

def import_pesticide_data():
    """Import pesticide data from Excel"""
    try:
        df1 = pd.read_excel('pesticide_data.xlsx')
        
        for index, row in df1.iterrows():
            # Clean NaN values
            row_data = {k: (v if pd.notna(v) else '') for k, v in row.items()}
            
            Pesticide.objects.create(
                pesticide=row_data.get('pesticide', ''),
                microorganism=row_data.get('microorganism', ''),
                phylum=row_data.get('phylum', ''),
                family=row_data.get('family', ''),
                strain=row_data.get('strain', ''),
                rrna_16s=row_data.get('rrna_16s', ''),
                tax_id=row_data.get('tax_id', ''),
                reference=row_data.get('reference', ''),
                category=row_data.get('category', ''),
                publication_year=row_data.get('publication_year'),
                substrate=row_data.get('substrate', ''),
                manufacturer=row_data.get('manufacturer', ''),
                evidence_by_microbe=row_data.get('evidence_by_microbe', ''),
                microbe_equipment=row_data.get('microbe_equipment', ''),
                isolation_environment=row_data.get('isolation_environment', ''),
                degradation_time_days=row_data.get('degradation_time_days', ''),
                isolation_location=row_data.get('isolation_location', ''),
                enzyme=row_data.get('enzyme', ''),
                evidence_of_enzyme=row_data.get('evidence_of_enzyme', ''),
                enzyme_equipment=row_data.get('enzyme_equipment', ''),
                gene=row_data.get('gene', ''),
                genbank_id=row_data.get('genbank_id', ''),
                enzyme_sequence=row_data.get('enzyme_sequence', ''),
            )
            
            if index % 100 == 0:
                print(f"Processed {index} records...")
        
        print(f"✅ Pesticide data imported. Total: {Pesticide.objects.count()} records")
        
    except FileNotFoundError:
        print("⚠️ Warning: pesticide_data.xlsx not found. Creating sample data...")
        # Create some sample data
        Pesticide.objects.create(
            pesticide="Atrazine",
            microorganism="Pseudomonas sp. ADP",
            category="Herbicide",
            publication_year=2000
        )
        print("✅ Sample pesticide data created")

def import_no_evidence_data():
    """Import no evidence pesticide data"""
    try:
        df2 = pd.read_excel('no_evidence_pesticides.xlsx')
        
        for _, row in df2.iterrows():
            NoEvidencePesticide.objects.create(
                pesticide=row.get('pesticide', ''),
                evidence_of_biodegradation=row.get('evidence_of_biodegradation', 'No evidence')
            )
        
        print(f"✅ NoEvidencePesticide data imported. Total: {NoEvidencePesticide.objects.count()} records")
        
    except FileNotFoundError:
        print("⚠️ Warning: no_evidence_pesticides.xlsx not found. Skipping...")

if __name__ == '__main__':
    import_pesticide_data()
    import_no_evidence_data()
    print("🎉 Data import completed!")