-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Sep 02, 2026 at 10:04 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `face_attendance_system`
--

-- --------------------------------------------------------

--
-- Table structure for table `students`
--

CREATE TABLE `students` (
  `id` int(11) NOT NULL,
  `student_id` varchar(50) NOT NULL,
  `full_name` varchar(100) NOT NULL,
  `department` varchar(50) DEFAULT NULL,
  `year` varchar(20) DEFAULT NULL,
  `semester` varchar(20) DEFAULT NULL,
  `email` varchar(100) DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `image` varchar(200) DEFAULT NULL,
  `registered_date` datetime DEFAULT current_timestamp(),
  `username` varchar(50) DEFAULT NULL,
  `password` varchar(100) DEFAULT NULL,
  `dob` date DEFAULT NULL,
  `nic` varchar(20) DEFAULT NULL,
  `gender` varchar(10) DEFAULT NULL,
  `religion` varchar(50) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `status` varchar(20) DEFAULT NULL,
  `part_time_full_time` varchar(20) DEFAULT 'Full Time'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `students`
--

INSERT INTO `students` (`id`, `student_id`, `full_name`, `department`, `year`, `semester`, `email`, `phone`, `image`, `registered_date`, `username`, `password`, `dob`, `nic`, `gender`, `religion`, `address`, `status`, `part_time_full_time`) VALUES
(117, 'NAW/IT/2324/F/0009', 'J.M.Oshadi Jayasekara', 'HNDIT', '2nd Year', 'II Semester', 'oshadi@gmail.com', '0755020108', 'c:\\Users\\New\\Desktop\\Face_Attendance_System2\\Face_Attendance_System\\face_attendance\\dataset\\NAW_IT_2324_F_0009_HNDIT\\preview.jpg', '2026-07-10 11:20:00', 'oshadi', '123', '2003-10-14', '200378810742', 'Female', 'Buddhism', 'Maldeniya', 'Active', 'Full Time'),
(122, 'NAW/IT/2324/F/0048', 'C.pracilla', 'HNDIT', '2nd Year', 'II Semester', '', '', 'c:\\Users\\New\\Desktop\\Face_Attendance_System2\\Face_Attendance_System\\face_attendance\\dataset\\NAW_IT_2324_F_0050_HNDIT\\preview.jpg', '2026-07-15 19:36:00', 'praci', '123', '2026-07-15', '202656780V', 'Female', 'Christianity', '', 'Active', 'Full Time'),
(124, 'NAW/THM/2324/F/0021', 'W.V.D.N.Kaushalya', 'HNDTHM', '2nd Year', 'II Semester', '', '', 'c:\\Users\\New\\Desktop\\Face_Attendance_System2\\Face_Attendance_System\\face_attendance\\dataset\\NAW_THM_2324_F_0021_HNDTHM\\preview.jpg', '2026-07-15 20:57:00', 'nirmani', '123', '2026-07-15', '202667780V', 'Female', 'Buddhism', '', 'Active', 'Full Time'),
(131, 'NAW/IT/2324/F/0047', 'L.R.Nelu Wasana', 'HNDIT', '2nd Year', 'II Semester', 'neluwasana8@gmail.com', '0755021040', 'c:\\Users\\New\\Desktop\\face_attendance_system 02\\Face_Attendance_System\\Face_Attendance_System\\face_attendance\\dataset\\NAW_IT_2324_F_0047_HNDIT\\preview.jpg', '2026-07-24 11:38:00', 'nelu', '123', '2002-09-19', '200276302837', 'Female', 'Buddhism', 'bandarawela', 'Active', 'Full Time');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `students`
--
ALTER TABLE `students`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `student_id` (`student_id`,`department`),
  ADD UNIQUE KEY `username` (`username`),
  ADD KEY `idx_student` (`student_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `students`
--
ALTER TABLE `students`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=132;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
