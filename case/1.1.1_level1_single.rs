//drop and use single 1-level variable
//DF:1
//UAF:1
fn main() {
    let leaf = Box::new(String::from("Hello"));
    let raw_ptr = Box::into_raw(leaf);
    unsafe{
        let r = Box::from_raw(raw_ptr);
        //drop(raw_ptr);
        std::ptr::drop_in_place(raw_ptr);
        
        println!("{:?}", &*r);
    }
}
