//DF:1
//UAF:0
#[derive(Debug)]
struct Root{
    node: Box<Node>,
    leaf: Box<i32>,
}

#[derive(Debug)]
struct Node{
    leaf: Box<i32>,
}

fn main() {
    let node = Node{leaf:Box::new(1)};
    let raw_ptr: *mut Node = Box::into_raw(Box::new(node));
    let r1 = Root{
        node: unsafe{Box::from_raw(raw_ptr)}, 
        leaf: Box::new(1)};
    let r2 = Root{
        node: unsafe{Box::from_raw(raw_ptr)}, 
        leaf: Box::new(1)};
    let ptr0 = & r2 as *const Root;
    let ptr1 = & *r2.node as *const Node;
    let ptr2 = & *r2.node.leaf as *const i32;
    let ptr3 = & *r2.leaf as *const i32;
    //
    //drop(r1);
    drop(r1.node);
    //drop(r1.node.leaf);
    unsafe{
        //println!("{:?}", &*ptr0);//accessing r2
        //println!("{:?}", &*ptr1);//accessing r2.node
        //println!("{:?}", &*ptr2);//accessing r2.node.leaf
        println!("{:?}", &*ptr3);//accessing r2.leaf
    }
}