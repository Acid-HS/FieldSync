//2 variables of Level 1- borrow
//DF:0
//UAF:1
fn main() {
    let leaf = Box::new(1);
    let raw_ptr = Box::into_raw(leaf);
    unsafe{
        let r1 = Box::from_raw(raw_ptr);
        let r2:&Box<i32> = std::mem::transmute(&r1);
        drop(r1);
        
        println!("{:?}", &*r2);
    }
}