use rocksdb::{DB, Options, DBWithThreadMode, SingleThreaded};

fn list_column_families(path: &str) {
    let cfs = rocksdb::DB::list_cf(&Options::default(), path)
        .expect("Failed to list column families");

    println!("Column Families found in {}:", path);
    for cf in cfs {
        println!(" - {}", cf);
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        eprintln!("Usage: sailfish_batch_cli <rocksdb_path>");
        std::process::exit(1);
    }

    let db_path = &args[1];
    list_column_families(db_path);
}

