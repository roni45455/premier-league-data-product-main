from src.extract import extract
from src.transform import transform
from src.load import load


def main():
    raw_matches = extract()

    transformed_matches = transform(raw_matches)

    final_data = load(transformed_matches)

    print(f"ETL completed")
    print(f"Processed rows: {len(final_data)}")


if __name__ == "__main__":
    main()