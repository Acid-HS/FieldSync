### Analysis Tool (Lazy_update Version)

The automated detection tool is implemented as a module of **RAPx** – a static analysis platform for Rust code.

#### Source Code

Core implementation: **`./tool/`**

#### Installation

1. Prerequisites: Ensure the Rust version specified in `rust-toolchain.toml` is installed.
2. One-step setup:
   
   ```shell
   ./install.sh
   ```
   
> Full installation guide: `./tool/README.md`

#### Usage

Run the analysis on any Rust project:

```shell
cargo rapx check -f
```

This will report results of field-sesitive check.

#### Effect

Here is an example of its effect:

```rust
//code snippet:
use std::ptr;
fn main() {
    let leaf = Box::new(1);
    let raw_ptr: *mut i32 = Box::into_raw(leaf);
    unsafe{
        let r1 = Box::from_raw(raw_ptr);
        {
         let r2 = Box::from_raw(raw_ptr);
         }
        println!("{:?}", &*r1);
    }
}
```

```shell
xx:xx:xx|RAP|INFO|: Start analysis with RAPx.
xx:xx:xx|RAP|INFO|: ================================
xx:xx:xx|RAP|INFO|: Aliases found: {DefId(2:12255 ~ core[b783]::fmt::rt::{impl#0}::new_debug): MopFnAliasPairs { arg_size: 1, alias_set: {MopAliasPair { fact: AliasPair { left_local: 0, lhs_fields: [0], right_local: 1, rhs_fields: [] }, lhs_may_drop: true, lhs_need_drop: false, rhs_may_drop: true, rhs_need_drop: false }} }, DefId(3:137 ~ alloc[9043]::alloc::{impl#0}::alloc_impl): MopFnAliasPairs { arg_size: 3, alias_set: {} }, DefId(2:27123 ~ core[b783]::ptr::non_null::{impl#3}::new_unchecked::precondition_check): MopFnAliasPairs { arg_size: 1, alias_set: {} }, DefId(3:671 ~ alloc[9043]::boxed::{impl#0}::new): MopFnAliasPairs { arg_size: 1, alias_set: {MopAliasPair { fact: AliasPair { left_local: 0, lhs_fields: [0], right_local: 1, rhs_fields: [] }, lhs_may_drop: true, lhs_need_drop: false, rhs_may_drop: true, rhs_need_drop: true }} }, DefId(2:12354 ~ core[b783]::fmt::{impl#4}::new): MopFnAliasPairs { arg_size: 2, alias_set: {MopAliasPair { fact: AliasPair { left_local: 0, lhs_fields: [1], right_local: 2, rhs_fields: [] }, lhs_may_drop: true, lhs_need_drop: false, rhs_may_drop: true, rhs_need_drop: false }, MopAliasPair { fact: AliasPair { left_local: 0, lhs_fields: [0], right_local: 1, rhs_fields: [] }, lhs_may_drop: true, lhs_need_drop: false, rhs_may_drop: true, rhs_need_drop: false }} }, DefId(3:748 ~ alloc[9043]::boxed::{impl#8}::into_raw): MopFnAliasPairs { arg_size: 1, alias_set: {MopAliasPair { fact: AliasPair { left_local: 0, lhs_fields: [], right_local: 1, rhs_fields: [0] }, lhs_may_drop: true, lhs_need_drop: false, rhs_may_drop: true, rhs_need_drop: false }} }, DefId(0:3 ~ sf_test[7453]::main): MopFnAliasPairs { arg_size: 0, alias_set: {} }, DefId(3:146 ~ alloc[9043]::alloc::exchange_malloc): MopFnAliasPairs { arg_size: 2, alias_set: {} }, DefId(3:746 ~ alloc[9043]::boxed::{impl#8}::from_raw): MopFnAliasPairs { arg_size: 1, alias_set: {MopAliasPair { fact: AliasPair { left_local: 0, lhs_fields: [0], right_local: 1, rhs_fields: [] }, lhs_may_drop: true, lhs_need_drop: false, rhs_may_drop: true, rhs_need_drop: false }} }}
xx:xx:xx|RAP|INFO|: Find a double free bug 4 during unwinding; add to records.
xx:xx:xx|RAP|WARN|: Find a use-after-free bug TyBug { drop_spot: LocalSpot { bb: Some(4), local: Some(7) }, trigger_info: LocalSpot { bb: Some(5), local: Some(4) }, prop_chain: [36, 38], span: src/main.rs:9:26: 9:30 (#0), confidence: 99 }; add to records
xx:xx:xx|RAP|WARN|: Find a use-after-free bug TyBug { drop_spot: LocalSpot { bb: Some(4), local: Some(7) }, trigger_info: LocalSpot { bb: Some(13), local: Some(17) }, prop_chain: [36, 38, 17], span: src/main.rs:9:19: 9:23 (#7), confidence: 99 }; add to records
xx:xx:xx|RAP|INFO|: Find a double free bug 4; add to records.
xx:xx:xx|RAP|WARN|: Double free detected in function "main"
xx:xx:xx|RAP|WARN|: Double free detected in function "main"
warning: Double free detected.
  --> src/main.rs:1:1
   |
 1 | / fn main() {
 2 | |     let leaf = Box::new(1);
 3 | |     let raw_ptr: *mut i32 = Box::into_raw(leaf);
 4 | |     unsafe{
 5 | |         let r1 = Box::from_raw(raw_ptr);
 6 | |         {
 7 | |          let _r2 = Box::from_raw(raw_ptr);
 8 | |          }
 9 | |         println!("{:?}", &*r1);
10 | |     }
11 | | }
   | |_- Double free (confidence 50%): Location in file src/main.rs line 1.
    | MIR detail: Value _7(_r2, src/main.rs:7) and _4(r1, src/main.rs:5) are alias.
    | MIR detail: _7(_r2, src/main.rs:7) is dropped at BB4(src/main.rs:8); _4(r1, src/main.rs:5) is dropped at BB8(src/main.rs:10).
   |
warning: Double free detected during unwinding.
  --> src/main.rs:1:1
   |
 1 | / fn main() {
 2 | |     let leaf = Box::new(1);
 3 | |     let raw_ptr: *mut i32 = Box::into_raw(leaf);
 4 | |     unsafe{
 5 | |         let r1 = Box::from_raw(raw_ptr);
 6 | |         {
 7 | |          let _r2 = Box::from_raw(raw_ptr);
 8 | |          }
 9 | |         println!("{:?}", &*r1);
10 | |     }
11 | | }
   | |_- Double free (confidence 50%): Location in file src/main.rs line 1.
    | MIR detail: Value _7(_r2, src/main.rs:7) and _4(r1, src/main.rs:5) are alias.
    | MIR detail: _7(_r2, src/main.rs:7) is dropped at BB4(src/main.rs:8); _4(r1, src/main.rs:5) is dropped at BB10(src/main.rs:10).
   |
xx:xx:xx|RAP|WARN|: Use-after-free detected in function "main"
warning: Use-after-free detected.
  --> src/main.rs:9:26
   |
 1 | fn main() {
 2 |     let leaf = Box::new(1);
 3 |     let raw_ptr: *mut i32 = Box::into_raw(leaf);
 4 |     unsafe{
 5 |         let r1 = Box::from_raw(raw_ptr);
 6 |         {
 7 |          let _r2 = Box::from_raw(raw_ptr);
 8 |          }
 9 |         println!("{:?}", &*r1);
   |                          ---- Use-after-free (confidence 99%): Location in file src/main.rs line 9.
    | MIR detail: Value _7(_r2, src/main.rs:7) and _4(r1, src/main.rs:5) are alias.
    | MIR detail: _7(_r2, src/main.rs:7) is dropped at BB4(src/main.rs:8); _4(r1, src/main.rs:5) is used at BB5(src/main.rs:9).
10 |     }
11 | }
   |
warning: Use-after-free detected.
  --> src/main.rs:9:19
   |
 1 | fn main() {
 2 |     let leaf = Box::new(1);
 3 |     let raw_ptr: *mut i32 = Box::into_raw(leaf);
 4 |     unsafe{
 5 |         let r1 = Box::from_raw(raw_ptr);
 6 |         {
 7 |          let _r2 = Box::from_raw(raw_ptr);
 8 |          }
 9 |         println!("{:?}", &*r1);
   |                   ---- Use-after-free (confidence 99%): Location in file src/main.rs line 9.
    | MIR detail: Value _7(_r2, src/main.rs:7) and _17(_, src/main.rs:9) are alias.
    | MIR detail: _7(_r2, src/main.rs:7) is dropped at BB4(src/main.rs:8); _17(_, src/main.rs:9) is used at BB13(src/main.rs:9).
10 |     }
11 | }
```

### Analysis Tool (Eager-Update Version)

#### Source Code

Eager-update version: **`./tool-eager/`**

#### Installation

For Eager-update version, get into **`./tool-demo/rapx/`** 

run 
```shell
cargo build
```

#### Usage

set environmental first:
```shell
export SYSROOT="$(rustc +nightly-2025-12-06 --print sysroot)"
export DYLD_LIBRARY_PATH="$SYSROOT/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
```
next:
```shell
$pathtothisversion/cargo-rapx rapx check -f
```

### Test Cases

The suite of test cases are in `case`.


#### Experiment
1. Create a new rust project **`test_tools`**
2. Copy folder **`./case`**(with 163 cases) and `./report/report_for_cases/bench_tools_com.py` into **`test_tools`**
3. Update the tool invocation command in `bench_tools_com.py` to a version compatible with your environment
```python
COMMANDS = [
    ("rapx", "cargo +nightly-2025-12-06 rapx check -f"),
    ("safedrop", "rustc +safedrop src/main.rs"),
    ("charon_rudra", "charon --ullbc && cargo-charon-rudra --file test_tools.ullbc"),
    ("miri", "cargo +nightly miri run"),
    ("kani", "cargo kani --output-format terse"),
]
```
4. Run `bench_tools_com.py` to get an individual report for all cases and an aggregate one