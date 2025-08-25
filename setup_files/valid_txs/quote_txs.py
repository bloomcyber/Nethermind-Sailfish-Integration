input_file = "valid_txs_part_4.txt"
output_file = "valid_txs_part_4_quoted.txt"

with open(input_file, "r") as fin, open(output_file, "w") as fout:
    for line in fin:
        tx = line.strip()
        if tx:
            fout.write(f'"{tx}"\n')
