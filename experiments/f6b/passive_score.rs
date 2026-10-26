//! F6-B: isolated Rust probe of F2-B's _score, NOT an embedded robot service.
//!
//! This is NOT a Rust port of AutonomyBrain: no perception validation, SQLite,
//! learning, cooldown, motors, networking or authentication. Pure f64 scoring
//! of prevalidated, fictional scalar inputs only. No dependencies beyond std.
//! rustc --edition=2021 --test experiments/f6b/passive_score.rs
//! rustc --edition=2021 -O experiments/f6b/passive_score.rs -o /tmp/f6b-score
//! /tmp/f6b-score --tsv    # read <= 2048 lines; seven TAB-separated fields
//! /tmp/f6b-score --bench  # host-only microbenchmark; not robot data

use std::hint::black_box;
use std::io::{self, Read};
use std::time::Instant;

const MAX_INPUT_BYTES: u64 = 131_072;
const MAX_ROWS: usize = 2048;
const MOTIVES: [f64; 5] = [0.75, 0.55, 0.60, 0.80, 0.35];
const INTENTS: [&str; 3] = ["observe", "inspect", "listen"];
const CATEGORIES: [&str; 5] = ["ball", "toy", "dog", "unknown", "knock"];
const ITERATIONS: usize = 120_000;

/// Input order: curiosity, sociability, play, energy, caution.
/// Exactly copies the ordering of terms in PassiveRhythm._score at the pinned
/// Companion revision. A match does NOT prove equivalent whole-brain behavior.
fn score(intent: &str, category: &str, m: &[f64; 5]) -> Result<f64, &'static str> {
    if !m.iter().all(|v| v.is_finite() && (0.0..=1.0).contains(v)) {
        return Err("motivation outside [0, 1]");
    }
    if category.is_empty() || category.len() > 24
        || !category.bytes().all(|b| b.is_ascii_lowercase() || b == b'_') {
        return Err("invalid fictional category token");
    }
    let fatigue = 1.0 - m[3];
    match intent {
        "observe" => {
            let toy_attention = if category == "ball" || category == "toy" {
                m[2] * 0.22
            } else {
                0.0
            };
            Ok(0.12 + 0.70 * m[0] + toy_attention
                - 0.45 * m[4] - 0.10 * fatigue)
        }
        "inspect" => Ok(0.13 + 0.80 * m[0]
                        - 0.55 * m[4] - 0.10 * fatigue),
        "listen" => Ok(0.18 + 0.80 * m[1]
                       - 0.28 * m[4] - 0.10 * fatigue),
        _ => Err("not a non-motor scoring intent"),
    }
}

fn parse_line(line: &str) -> Result<f64, &'static str> {
    let parts: Vec<_> = line.split('\t').collect();
    if parts.len() != 7 {
        return Err("expected 7 tab-separated fields");
    }
    let mut m = [0.0_f64; 5];
    for i in 0..5 {
        m[i] = parts[i + 2].parse::<f64>().map_err(|_| "invalid decimal")?;
    }
    score(parts[0], parts[1], &m)
}

fn run_tsv() -> Result<(), &'static str> {
    let mut bytes = Vec::new();
    let mut stdin = io::stdin().lock();
    // Cap entire fixture read; no sensor or untrusted network ingress.
    stdin.take(MAX_INPUT_BYTES + 1)
        .read_to_end(&mut bytes).map_err(|_| "stdin read error")?;
    if bytes.len() as u64 > MAX_INPUT_BYTES {
        return Err("fixture byte limit exceeded");
    }
    let text = std::str::from_utf8(&bytes).map_err(|_| "invalid utf8")?;
    let rows: Vec<&str> = text.lines().collect();
    if rows.len() > MAX_ROWS {
        return Err("fixture row limit exceeded");
    }
    let mut results = Vec::with_capacity(rows.len());
    for row in rows {
        if row.len() > 256 || row.is_empty() {
            return Err("invalid fixture line length");
        }
        results.push(parse_line(row)?);
    }
    // Do not print partial scores for a malformed multi-line fixture.
    for s in results {
        println!("{:.17e}", s);
    }
    Ok(())
}

fn run_bench() {
    let begin = Instant::now();
    let mut checksum = 0.0;
    for i in 0..ITERATIONS {
        // Same deterministic iteration order as the Python baseline.
        let intent = black_box(INTENTS[i % INTENTS.len()]);
        let category = black_box(CATEGORIES[i % CATEGORIES.len()]);
        checksum += black_box(score(intent, category, &MOTIVES).unwrap());
    }
    println!(
        "{{\"iterations\":{},\"checksum\":{:.17e},\"loop_wall_ms\":{:.6},\"kind\":\"host_rust_pure_probe\",\"physical_robot_validated\":false}}",
        ITERATIONS, checksum, begin.elapsed().as_secs_f64() * 1000.0
    );
}

fn main() {
    let mut args = std::env::args();
    let _name = args.next();
    let command = args.next();
    if args.next().is_some() {
        eprintln!("F6-B probe: one command only");
        std::process::exit(2);
    }
    match command.as_deref() {
        Some("--tsv") => {
            if let Err(reason) = run_tsv() {
                eprintln!("F6-B rejected fictional input: {reason}");
                std::process::exit(2);
            }
        }
        Some("--bench") => run_bench(),
        _ => {
            eprintln!("F6-B: use --tsv or --bench; never controls robot hardware");
            std::process::exit(2);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_scores_are_finite_and_pure() {
        for action in INTENTS {
            for category in CATEGORIES {
                let v = score(action, category, &MOTIVES).unwrap();
                assert!(v.is_finite());
            }
        }
        assert!(score("observe", "ball", &MOTIVES).unwrap()
            > score("observe", "dog", &MOTIVES).unwrap());
        assert_eq!(score("listen", "meow", &MOTIVES).unwrap(),
                   score("listen", "bark", &MOTIVES).unwrap());
    }

    #[test]
    fn refuse_motor_and_pc_intents() {
        for action in ["robot.move", "robot.stop", "explore", "head", "pc", "halt", "rest"] {
            assert!(score(action, "ball", &MOTIVES).is_err());
        }
    }

    #[test]
    fn refuse_invalid_numbers() {
        for bad in [-0.01, 1.01, f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            for i in 0..5 {
                let mut m = MOTIVES;
                m[i] = bad;
                assert!(score("observe", "ball", &m).is_err());
            }
        }
    }

    #[test]
    fn reject_unbounded_categories_and_bad_tsv() {
        assert!(score("observe", "track-001", &MOTIVES).is_err());
        assert!(score("observe", "a very long private free form", &MOTIVES).is_err());
        assert!(parse_line("observe\tball\t0.75\t0.55").is_err());
        assert!(parse_line("robot.move\tball\t0.75\t0.55\t0.6\t0.8\t0.35").is_err());
        assert!(parse_line("observe\tball\tNaN\t0.55\t0.6\t0.8\t0.35").is_err());
    }
}
