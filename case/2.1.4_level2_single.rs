//DF:0
//UAF:0
#[derive(Debug)]
struct Node{
    leaf1: Box<i32>,
    leaf2: Box<i32>,
}

fn main() {
    let leaf = Box::new(1);
    let raw_ptr: *mut i32 = Box::into_raw(leaf);
    let r1 = Node{
        leaf1: unsafe{Box::from_raw(raw_ptr)}, 
        leaf2: Box::new(1)};
    let ptr0 = & r1 as *const Node;
    let ptr1 = & *r1.leaf1 as *const i32;
    let ptr2 = & *r1.leaf2 as *const i32;

    drop(r1);
    //drop(r1.leaf1);
    //drop(r1.leaf2);

    unsafe{
        //println!("{:?}", &*ptr0);//accessing r1
        //println!("{:?}", &*ptr1);//accessing r1.leaf1
        //println!("{:?}", &*ptr2);//accessing r1.leaf2
    }
}