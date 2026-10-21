//DF:0
//UAF:1
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
    //let node = Node{leaf:Box::new(1)};
    //let raw_ptr: *mut Node = Box::into_raw(Box::new(node));
    let raw_ptr: *mut Node = Box::into_raw(Box::new(Node{leaf:Box::new(1)}));
    let r = Root{
        node: unsafe{Box::from_raw(raw_ptr)}, 
        leaf: Box::new(1)};
    let ptr0 = & r as *const Root;
    let ptr1 = & *r.node as *const Node;
    let ptr2 = & *r.node.leaf as *const i32;
    let ptr3 = & *r.leaf as *const i32;

    //drop(r);
    //drop(r.node);
    drop(r.node.leaf);

    unsafe{
        //println!("{:?}", &*ptr0);//accessing r
        println!("{:?}", &*ptr1);//accessing r.node
        //println!("{:?}", &*ptr2);//accessing r.node.leaf1
        //println!("{:?}", &*ptr3);//accessing r.leaf
    }
}