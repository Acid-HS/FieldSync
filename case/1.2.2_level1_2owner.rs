//2 variables of Level 1
//DF:1
//UAF:0
fn main() {
    let leaf = Box::new(1);
    let raw_ptr: *mut i32 = Box::into_raw(leaf);
    unsafe{
        let r1 = Box::from_raw(raw_ptr);

        //drop part
        let r2 = Box::from_raw(raw_ptr);
        drop(r2);//drop way 3.2
        
        //use part
        //println!("{:?}", &*r1);
    }
}