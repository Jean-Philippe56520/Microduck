//! PER-P8 host-only parity probe. Not a daemon, not used by robotd or mediad.
//! Strict tensor sizes, no network, no camera, no model loading, no motors.
use std::{env, fs, io::Write as _, path::Path};

use kwipi_seg_mask_core::{OUTPUT0_LEN, OUTPUT1_LEN, decode};

fn read_le_f32(path: &Path, wanted: usize) -> Result<Vec<f32>, String> {
    let bytes = fs::read(path).map_err(|e| format!("input read failed: {e}"))?;
    let size = wanted.checked_mul(4).ok_or("invalid input size")?;
    if bytes.len() != size {
        return Err(format!(
            "input tensor length {} does not match strict contract {size}",
            bytes.len()
        ));
    }
    Ok(bytes
        .chunks_exact(4)
        .map(|chunk| f32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]))
        .collect())
}

fn do_probe(args: &[String]) -> Result<(), String> {
    if args.len() != 4 {
        return Err(
            "usage: kwipi-rust-parity-probe DECODED_F32_LE PROTO_F32_LE MASKS_U8_OUT".to_owned(),
        );
    }
    let decoded = read_le_f32(Path::new(&args[1]), OUTPUT0_LEN)?;
    let protos = read_le_f32(Path::new(&args[2]), OUTPUT1_LEN)?;
    let found = decode(&decoded, &protos, 0.25, 10)
        .map_err(|err| format!("core refused tensor pair: {err:?}"))?;
    let total = found.iter().map(|c| c.mask_160.len()).sum::<usize>();
    if total > 256_000 {
        return Err("out-of-contract mask allocation".to_owned());
    }
    // Write only after every input and candidate has passed validation.
    let out_path = Path::new(&args[3]);
    let mut file = fs::File::create(out_path).map_err(|e| format!("output failed: {e}"))?;
    for candidate in &found {
        file.write_all(&candidate.mask_160)
            .map_err(|e| format!("mask write failed: {e}"))?;
    }
    let classes: Vec<String> = found
        .iter()
        .map(|c| c.proposed_class_id.to_string())
        .collect();
    let scores: Vec<String> = found.iter().map(|c| c.score.to_string()).collect();
    let boxes: Vec<String> = found
        .iter()
        .map(|c| {
            format!(
                "[{},{},{},{}]",
                c.box_model_xyxy[0], c.box_model_xyxy[1], c.box_model_xyxy[2], c.box_model_xyxy[3]
            )
        })
        .collect();
    let nonempty = found.iter().filter(|c| c.foreground_pixels > 0).count();
    println!(
        "{{\"count\":{},\"classes\":[{}],\"scores\":[{}],\"boxes\":[{}],\"nonempty\":{}}}",
        found.len(),
        classes.join(","),
        scores.join(","),
        boxes.join(","),
        nonempty
    );
    Ok(())
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if let Err(reason) = do_probe(&args) {
        eprintln!("PER-P8 refusal: {reason}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn no_arguments_refused() {
        assert!(do_probe(&["probe".to_string()]).is_err());
    }

    #[test]
    fn input_length_mismatch_refused() {
        let mut file = env::temp_dir();
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        file.push(format!(
            "kwipi-p8-bad-tensor-{}-{now}.bin",
            std::process::id()
        ));
        fs::write(&file, [0_u8; 3]).unwrap();
        let result = read_le_f32(&file, OUTPUT0_LEN);
        fs::remove_file(&file).unwrap();
        assert!(result.unwrap_err().contains("length"));
    }
}
