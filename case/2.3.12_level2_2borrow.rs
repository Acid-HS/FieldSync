//level2-2 borrows
//DF:1
//UAF:0
#[derive(Debug)]
struct Node{
    leaf1: Box<i32>,
    leaf2: Box<i32>,
}

#[derive(Debug)]
struct Node1<'a>{
    leaf1: &'a Box<i32>,
    leaf2: Box<i32>,
}

fn main() {
    let r1 = Node{
        leaf1: Box::new(1), 
        leaf2: Box::new(1)};
    let r2 = Node1{
        leaf1: unsafe{std::mem::transmute(&r1.leaf1)}, 
        leaf2: Box::new(1)};
    let ptr0 = &r2 as *const Node1;
    let ptr1 = & **r2.leaf1 as *const i32;
    let ptr2 = & *r2.leaf2 as *const i32;

    //drop(r1);
    //drop(r1.leaf1);
    drop(r1.leaf2);

    unsafe{
        //println!("{:?}", &*ptr0);//accessing r3
        //println!("{:?}", &*ptr1);//accessing r3.leaf1
        //println!("{:?}", &*ptr2);//accessing r3.leaf2
    }
}