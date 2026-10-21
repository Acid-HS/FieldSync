//cross 3 variables - shared ownership
//DF:2
//UAF:1
fn main() {
    let leaf = Box::new(1);
    let raw_ptr = Box::into_raw(leaf);
    unsafe{
        let r1 = Box::from_raw(raw_ptr);
        let r2 = Box::from_raw(raw_ptr);

        let r3 = Box::from_raw(raw_ptr);
        drop(r1);

        println!("{:?}", &*r2);
    }
}