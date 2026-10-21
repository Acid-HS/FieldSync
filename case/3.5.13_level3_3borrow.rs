//DF:2
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
    let r1 = Root{
        node: Box::new(Node{leaf:Box::new(1)}), 
        leaf: Box::new(1)};
    let r2 = Root{
        node: unsafe{std::mem::transmute(&r1.node)}, 
        leaf: Box::new(1)};
    let r3 = Root{
        node: unsafe{std::mem::transmute(&r2.node)}, 
        leaf: Box::new(1)};
    let ptr0 = & r3 as *const Root;
    let ptr1 = & *r3.node as *const Node;
    let ptr2 = & *r3.node.leaf as *const i32;
    let ptr3 = & *r3.leaf as *const i32;
    //
    //drop(r1);
    //drop(r1.node);
    drop(r1.node.leaf);
    unsafe{
        //println!("{:?}", &*ptr0);//accessing r3
        //println!("{:?}", &*ptr1);//accessing r3.node
        println!("{:?}", &*ptr2);//accessing r3.node.leaf
        //println!("{:?}", &*ptr3);//accessing r3.leaf
    }
}