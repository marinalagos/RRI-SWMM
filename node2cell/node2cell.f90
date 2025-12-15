! Mapping the node of the sewage network to RRI cells
! 20251007 by Menglu Qin 


Program node2cell
implicit none

character*256 infile
character*256 outfile_node_ij ! output file of the cell index (i,j) of each node
character*256 outfile_numnode ! Distribution basin map of node number in each cell
parameter(infile = "set_node2cell.txt") !setting file for this Program
parameter(outfile_node_ij = "node_ij.txt")
parameter(outfile_numnode = "numnode.asc")

character*256 node_cord_file !input file of node coordinates
character*256 rri_cell_file  !input file of the basin map in cell format

real(8) xllcorner_rri,xurcorner_rri
real(8) yllcorner_rri,yurcorner_rri
real(8) cellsize_rri, nodata
integer nrows_rri
integer ncols_rri
integer totalnode
integer i,j,k,ios,m
character*256, allocatable:: nodeID(:)
real(8), allocatable :: node_x(:), node_y(:)
integer, allocatable :: node_i(:), node_j(:)
integer, allocatable :: numnodincell(:,:)
character*256 header1, header2, header3, header4, header5, header6, ctemp
real(8) dummy

! read the setting file
open(1, file=infile, status='old', action='read', iostat=ios)
if (ios /= 0) then
    write(*,*) 'Error opening the setting file:', infile
    stop
end if
read(1,*) node_cord_file
read(1,*) rri_cell_file 
close(1)
write(*,*) 'Node coordinate file: ', node_cord_file
write(*,*) 'RRI cell file: ', rri_cell_file 
write(*, *) 'Output file of node (i,j): ', outfile_node_ij
write(*, *) 'Output file of distribution map of node number in each cell: ', outfile_numnode
write(*,*) 'Finish reading the setting file.'



!read node coordinates
open (2, file=node_cord_file, status='old', action='read', iostat=ios)
totalnode = -1
do 
    read(2,*,iostat=ios)
    if (ios /= 0) exit
    totalnode = totalnode + 1    
end do
close(2)
write(*,*) 'Total node number: ', totalnode
allocate(nodeID(totalnode))
allocate(node_x(totalnode),node_y(totalnode))
allocate(node_i(totalnode),node_j(totalnode))
node_x = 0.0d0
node_y = 0.0d0 
node_i = 0
node_j = 0

open (2, file=node_cord_file, status='old')
read(2,*) ctemp, ctemp, ctemp! read the first line
do k = 1, totalnode
    read(2,*) nodeID(k), node_x(k), node_y(k)
end do 
close(2)
write(*,*) 'Finish reading node coordinates.'

! read the RRI cell file
open(3, file=rri_cell_file, status='old', action='read', iostat=ios)
if (ios /= 0) then
    write(*,*) 'Error opening the RRI cell file: ', rri_cell_file
    stop
end if
read(3,*) header1, ncols_rri ! number of columns; x:j in RRI
read(3,*) header2, nrows_rri ! number of rows; y: i in RRI
read(3,*) header3, xllcorner_rri ! x coordinate of the lower left corner
read(3,*) header4, yllcorner_rri ! y coordinate of the lower left corner
read(3,*) header5, cellsize_rri ! cell size
read(3,*) header6, nodata ! no data value
write(*,*) 'Total number of x (j): ', ncols_rri
write(*,*) 'Total number of y (i): ', nrows_rri
write(*,*) 'x coordinate of the lower left corner: ', xllcorner_rri
write(*,*) 'y coordinate of the lower left corner: ', yllcorner_rri
write(*,*) 'cell size: ', cellsize_rri

write(*,*) 'Finish reading the RRI cell file header.'
allocate(numnodincell(nrows_rri, ncols_rri))
numnodincell = 0

do i = 1, nrows_rri
    read(3,*) (numnodincell(i,j), j=1,ncols_rri) ! read the cell values but not used
end do
close(3)
! map the node to cell index (i,j)
where(numnodincell > 0) numnodincell = 0

xurcorner_rri = xllcorner_rri + ncols_rri*cellsize_rri
yurcorner_rri = yllcorner_rri + nrows_rri*cellsize_rri
write(*,*) 'x coordinate of the upper right corner: ', xurcorner_rri    
write(*,*) 'y coordinate of the upper right corner: ', yurcorner_rri

open(4, file=outfile_node_ij, status='replace', action='write', iostat=ios)
if (ios /= 0) then  
    write(*,*) 'Error opening the output file: ', outfile_node_ij
    stop
end if
write(4,*) 'NodeID, i(y), j(x)'
m=0
do k = 1, totalnode
    if (node_x(k) < xllcorner_rri .or. node_x(k) > xurcorner_rri .or. &
        node_y(k) < yllcorner_rri .or. node_y(k) > yurcorner_rri) then
        !write(*,*) 'Node ', nodeID(k), ' is out of the RRI domain.'
        m = m + 1
        cycle
    end if
    node_j(k) = int((node_x(k) - xllcorner_rri)/cellsize_rri) + 1 ! column index
    node_i(k) = int((node_y(k) - yllcorner_rri)/cellsize_rri) + 1 ! row index
   ! write(*,*) 'Node ', nodeID(k), ' (', node_x(k), ',', node_y(k), &
    !           ') is in cell (i,j)=(', i,',', j,')'
    write(4,'(a10, 2i8)') nodeID(k), node_i(k), node_j(k)
end do
close(4)
if(m > 0) then
    write(*,*) m, ' nodes are out of the RRI domain.'
else
    write(*,*) 'All nodes are mapped to the RRI domain.'
end if

write(*,*) 'Finish mapping nodes to RRI cells. Output file: ', outfile_node_ij
! count the number of nodes in each cell

m=0
do k = 1, totalnode
    if (node_i(k) > 0 .and. node_i(k) <= nrows_rri .and. &
        node_j(k) > 0 .and. node_j(k) <= ncols_rri) then
        numnodincell(node_i(k), node_j(k)) = numnodincell(node_i(k), node_j(k)) + 1
        m = m + 1
    end if
end do 
if(m /= totalnode) then
    write(*,*) totalnode-m, ' nodes are mapped to the RRI domain.'
else
    write(*,*) 'All nodes are mapped to the RRI domain.'
end if

! output the distribution map of node number in each cell
open(5, file=outfile_numnode, status='replace', action='write', iostat=ios)
if (ios /= 0) then  
    write(*,*) 'Error opening the output file: ', outfile_numnode
    stop
end if  
!write(5,*) 'ncols ', ncols_rri
!write(5,*) 'nrows ', nrows_rri
!write(5,*) 'xllcorner ', xllcorner_rri
!write(5,*) 'yllcorner ', yllcorner_rri
!write(5,*) 'cellsize ', cellsize_rri
!write(5,*) 'NODATA_value ', nodata
write(5,'(a10, i8)') header1, ncols_rri
write(5,'(a10, i8)') header2, nrows_rri
write(5,'(a10, f20.7)') header3, xllcorner_rri
write(5,'(a10, f20.7)') header4, yllcorner_rri
write(5,'(a10, f20.7)') header5, cellsize_rri
write(5,'(a10, f20.7)') header6, nodata
!do i = nrows_rri, 1, -1
do  i = 1, nrows_rri
    write(5,'(10000i10)') (numnodincell(i,j), j=1,ncols_rri)
end do
close(5)
write(*,*) 'Finish writing the distribution map of node number in each cell. Output file: ', outfile_numnode
deallocate(nodeID)
deallocate(node_x,node_y)   
deallocate(node_i,node_j)
deallocate(numnodincell)
end program node2cell


