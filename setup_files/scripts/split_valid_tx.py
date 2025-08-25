def split_file(input_path, output_prefix, parts=4):
    with open(input_path, "r") as f:
        lines = f.readlines()

    total = len(lines)
    chunk = total // parts
    assert total % parts == 0, "File does not divide evenly into 4 parts."

    for i in range(parts):
        start = i * chunk
        end = (i + 1) * chunk
        output_path = f"{output_prefix}_{i+1}.txt"
        with open(output_path, "w") as out:
            out.writelines(lines[start:end])
        print(f"✅ Wrote {end - start} txs to {output_path}")


# Example usage
split_file("single_nonce_valid_txs.json", "valid_txs_part")
